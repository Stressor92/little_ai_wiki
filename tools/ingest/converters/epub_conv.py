"""
converters/epub_conv.py
EPUB/EPUB3 → Markdown via ebooklib + BeautifulSoup

Verarbeitet:
  - Kapitelreihenfolge aus Spine + NCX/NAV
  - HTML-Struktur (h1-h6, p, ul, ol, blockquote, table)
  - Metadaten aus OPF
"""

from __future__ import annotations
import logging
import re
from pathlib import Path

from .base import (
    BaseConverter, Block, BlockType, Chapter,
    Document, DocumentMeta,
)
from .html_utils import html_to_blocks

log = logging.getLogger(__name__)


class EPUBConverter(BaseConverter):
    SUPPORTED_EXTENSIONS = (".epub",)

    def convert(self, input_path: Path) -> Document:
        try:
            import ebooklib
            from ebooklib import epub
        except ImportError:
            raise ImportError("ebooklib fehlt: pip install ebooklib")

        book = epub.read_epub(str(input_path), options={"ignore_ncx": False})
        meta = self._extract_meta(book, input_path)
        doc  = Document(meta=meta)

        # Kapitelreihenfolge aus Spine
        items_by_id = {item.id: item for item in book.items}
        spine_ids   = [sid for sid, _ in book.spine]

        chapters_html = []
        for sid in spine_ids:
            item = items_by_id.get(sid)
            if item and item.media_type == "application/xhtml+xml":
                chapters_html.append(item)

        # Fallback: alle DOCUMENT-Items wenn Spine leer
        if not chapters_html:
            chapters_html = [
                i for i in book.items
                if i.get_type() == ebooklib.ITEM_DOCUMENT
            ]

        log.info(f"EPUB: {len(chapters_html)} Kapitel-Dateien")

        for item in chapters_html:
            try:
                content = item.get_content().decode("utf-8", errors="replace")
                blocks  = html_to_blocks(content)

                # Ersten H1-Block als Kapitelname verwenden
                chapter_title = self._find_chapter_title(item.get_name(), blocks)
                chapter = doc.add_chapter(chapter_title)

                # H1 am Anfang nicht doppelt einfügen
                skip_first_h1 = True
                for block in blocks:
                    if skip_first_h1 and block.type == BlockType.HEADING_1:
                        skip_first_h1 = False
                        continue
                    chapter.blocks.append(block)

            except Exception as e:
                log.warning(f"EPUB Kapitel Fehler ({item.get_name()}): {e}")

        doc.meta.chapters = len(doc.chapters)
        return doc

    # ── Metadaten ─────────────────────────────────────────────────────────────

    def _extract_meta(self, book, path: Path) -> DocumentMeta:
        def get(key: str) -> str:
            val = book.get_metadata("DC", key)
            if val:
                content = val[0][0] if isinstance(val[0], tuple) else str(val[0])
                return str(content).strip()
            return ""

        return DocumentMeta(
            title       = get("title")       or path.stem,
            author      = get("creator")     or "",
            publisher   = get("publisher")   or "",
            date        = get("date")        or "",
            language    = get("language")    or "",
            description = get("description") or "",
            isbn        = get("identifier")  or "",
            source_file = path.name,
            source_fmt  = "EPUB",
        )

    def _find_chapter_title(self, filename: str, blocks: list[Block]) -> str:
        for block in blocks[:5]:
            if block.type in (BlockType.HEADING_1, BlockType.HEADING_2):
                return block.text
        # Aus Dateiname ableiten
        name = Path(filename).stem
        name = re.sub(r'[-_]', ' ', name).strip()
        name = re.sub(r'\s+', ' ', name)
        return name.title() if name else "Kapitel"
