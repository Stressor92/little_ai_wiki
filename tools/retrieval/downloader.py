"""
Downloader: Lädt PDFs/HTML nach 00_raw_medical/{source}/
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional, Dict, List

import aiohttp

from tools.shared.config import RAW_DIR
from tools.shared.database import mark_downloaded

log = logging.getLogger(__name__)


class Downloader:
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; HealthWikiBot/1.0; "
            "+https://github.com/user/health-wiki)"
        )
    }

    def __init__(self, session: aiohttp.ClientSession, db_path: Path):
        self.session  = session
        self.db_path  = db_path
        self._sema    = asyncio.Semaphore(3)

    async def download_paper(self, paper: Dict) -> Optional[Path]:
        """Versucht PDF > Fulltext > DOI. Gibt Pfad oder None zurück."""
        urls = [
            paper.get("pdf_url"),
            paper.get("fulltext_url"),
            (f"https://doi.org/{paper['doi']}" if paper.get("doi") else None),
        ]
        urls = [u for u in urls if u]

        for url in urls:
            path = await self._try_download(paper, url)
            if path:
                mark_downloaded(self.db_path, paper["source_key"], str(path))
                return path
        return None

    async def _try_download(self, paper: Dict, url: str) -> Optional[Path]:
        async with self._sema:
            try:
                async with self.session.get(
                    url,
                    headers=self.HEADERS,
                    allow_redirects=True,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        return None
                    ct = resp.headers.get("Content-Type", "")
                    is_pdf = "pdf" in ct or url.lower().endswith(".pdf")
                    if not is_pdf and "html" not in ct:
                        return None

                    content = await resp.read()
                    if len(content) < 1024:
                        return None

                    ext  = ".pdf" if is_pdf else ".html"
                    dest = self._dest_path(paper, ext)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(content)
                    log.info(f"✓ {dest.relative_to(RAW_DIR.parent.parent)}")
                    return dest

            except Exception as e:
                log.debug(f"Download failed ({url[:60]}): {e}")
                return None

    def _dest_path(self, paper: Dict, ext: str) -> Path:
        """
        00_raw_medical/
          {source}/
            {year}_{ext_id}_{safe_title}{ext}
        """
        source   = paper.get("source", "unknown")
        year     = paper.get("year", "0000")
        ext_id   = re.sub(r'[^\w]', '', str(paper.get("external_id", "")))[:15]
        title    = re.sub(r'[^\w\s-]', '', paper.get("title", "")[:50]).strip()
        title    = re.sub(r'\s+', '_', title)
        filename = f"{year}_{ext_id}_{title}{ext}"
        return RAW_DIR / source / filename


async def download_batch(
    papers: List[Dict],
    db_path: Path,
    max_downloads: int = 100,
) -> int:
    """Lädt Open-Access-Paper herunter. Gibt Erfolgsanzahl zurück."""
    queue = [
        p for p in papers
        if not p.get("downloaded") and p.get("is_open_access")
    ][:max_downloads]

    if not queue:
        log.info("Keine neuen Open-Access-Paper zum Downloaden.")
        return 0

    log.info(f"Download: {len(queue)} Paper...")

    async with aiohttp.ClientSession() as session:
        dl = Downloader(session, db_path)
        results = await asyncio.gather(
            *[dl.download_paper(p) for p in queue],
            return_exceptions=True,
        )

    success = sum(1 for r in results if r and not isinstance(r, Exception))
    log.info(f"Downloads: {success}/{len(queue)} erfolgreich")
    return success
