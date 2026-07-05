"""
converters/html_conv.py
HTML → Markdown

converters/calibre_conv.py
MOBI / AZW3 / LIT / FB2 → Markdown via Calibre CLI (ebook-convert)
Fallback: mobi Python-Bibliothek für MOBI
"""

from __future__ import annotations
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .base import BaseConverter, Block, BlockType, Document, DocumentMeta
from .html_utils import html_to_blocks

log = logging.getLogger(__name__)


# ─── HTML Converter ───────────────────────────────────────────────────────────

class HTMLConverter(BaseConverter):
    SUPPORTED_EXTENSIONS = (".html", ".htm", ".xhtml")

    def convert(self, input_path: Path) -> Document:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("beautifulsoup4 fehlt: pip install beautifulsoup4 lxml")

        content = input_path.read_text(encoding="utf-8", errors="replace")
        soup    = BeautifulSoup(content, "lxml")

        # Metadaten aus <head>
        meta = self._extract_meta(soup, input_path)
        doc  = Document(meta=meta)

        # Körper verarbeiten
        body = soup.find("body") or soup
        blocks = html_to_blocks(str(body))

        # H1-Blöcke als Kapitel-Trenner nutzen
        current_chapter = doc.add_chapter(meta.title or input_path.stem)
        first_h1 = True

        for block in blocks:
            if block.type == BlockType.HEADING_1:
                if first_h1:
                    first_h1 = False
                    current_chapter.title = block.text
                else:
                    current_chapter = doc.add_chapter(block.text)
            else:
                current_chapter.blocks.append(block)

        doc.meta.chapters = len(doc.chapters)
        return doc

    def _extract_meta(self, soup, path: Path) -> DocumentMeta:
        def meta_content(name: str) -> str:
            tag = (soup.find("meta", attrs={"name": name})
                   or soup.find("meta", property=f"og:{name}"))
            return (tag.get("content", "") if tag else "").strip()

        title_tag = soup.find("title")
        return DocumentMeta(
            title       = (title_tag.get_text() if title_tag else "") or path.stem,
            author      = meta_content("author"),
            description = meta_content("description"),
            source_file = path.name,
            source_fmt  = "HTML",
        )


# ─── Calibre Converter (MOBI, AZW3, LIT, FB2, …) ─────────────────────────────

class CalibreConverter(BaseConverter):
    """
    Nutzt Calibres `ebook-convert` CLI um exotische Formate zuerst
    in EPUB umzuwandeln, dann den EPUBConverter zu verwenden.

    Calibre installieren: https://calibre-ebook.com/download
    Oder: apt install calibre
    """

    SUPPORTED_EXTENSIONS = (".mobi", ".azw", ".azw3", ".lit", ".fb2",
                             ".lrf", ".pdb", ".cbz", ".cbr")

    def convert(self, input_path: Path) -> Document:
        if self._has_calibre():
            return self._via_calibre(input_path)

        # Fallback für MOBI: direkte Python-Bibliothek
        if input_path.suffix.lower() == ".mobi":
            return self._via_mobi_lib(input_path)

        raise RuntimeError(
            f"Calibre (ebook-convert) nicht gefunden.\n"
            f"Installieren: https://calibre-ebook.com/download\n"
            f"Oder: sudo apt install calibre"
        )

    def _has_calibre(self) -> bool:
        try:
            result = subprocess.run(
                ["ebook-convert", "--version"],
                capture_output=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _via_calibre(self, input_path: Path) -> Document:
        from .epub_conv import EPUBConverter

        log.info(f"Calibre: konvertiere {input_path.name} → EPUB...")

        with tempfile.TemporaryDirectory() as tmp:
            epub_path = Path(tmp) / f"{input_path.stem}.epub"

            result = subprocess.run(
                [
                    "ebook-convert",
                    str(input_path),
                    str(epub_path),
                    "--no-default-epub-cover",
                    "--pretty-print",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                log.error(f"Calibre Fehler:\n{result.stderr}")
                raise RuntimeError(f"ebook-convert fehlgeschlagen: {result.stderr[:500]}")

            if not epub_path.exists():
                raise RuntimeError("Calibre: kein Output-EPUB erstellt")

            doc = EPUBConverter().convert(epub_path)

        # Source-Metadaten korrigieren
        doc.meta.source_file = input_path.name
        doc.meta.source_fmt  = input_path.suffix.upper().lstrip(".")
        return doc

    def _via_mobi_lib(self, input_path: Path) -> Document:
        """Direktes MOBI-Parsing ohne Calibre."""
        try:
            import mobi
        except ImportError:
            raise ImportError(
                "mobi-Bibliothek fehlt: pip install mobi\n"
                "Oder Calibre installieren für beste Ergebnisse."
            )

        from .html_utils import html_to_blocks
        from .epub_conv import EPUBConverter

        log.info("MOBI: direktes Parsing (ohne Calibre)...")

        extracted = mobi.extract(str(input_path))
        temp_root: Path | None = None

        if isinstance(extracted, tuple):
            temp_root = Path(extracted[0]) if extracted and extracted[0] else None
            outpath = Path(extracted[1])
        else:
            outpath = Path(extracted)

        try:
            if outpath.exists() and outpath.suffix.lower() == ".epub":
                doc = EPUBConverter().convert(outpath)
                doc.meta.source_file = input_path.name
                doc.meta.source_fmt = "MOBI"
                return doc

            if outpath.exists() and outpath.suffix.lower() in (".html", ".htm", ".xhtml"):
                content = outpath.read_text(encoding="utf-8", errors="replace")
            else:
                raise RuntimeError("MOBI extraction did not yield EPUB/HTML output.")

            meta   = self._make_meta(input_path, "MOBI")
            doc    = Document(meta=meta)
            blocks = html_to_blocks(content)

            chapter = doc.add_chapter(meta.title)
            for block in blocks:
                if block.type == BlockType.HEADING_1:
                    chapter = doc.add_chapter(block.text)
                else:
                    chapter.blocks.append(block)

            doc.meta.chapters = len(doc.chapters)
            return doc
        finally:
            if temp_root is not None and temp_root.exists():
                shutil.rmtree(temp_root, ignore_errors=True)


# ─── TXT Converter ────────────────────────────────────────────────────────────

class TXTConverter(BaseConverter):
    """
    Plain Text → Markdown mit heuristischer Struktur-Erkennung.
    Erkennt: Kapitelzeilen (Großbuchstaben / Nummerierung / kurze Zeilen),
             Absätze (Leerzeilen), Listen (- / * / Zahlen).
    """

    SUPPORTED_EXTENSIONS = (".txt", ".text", ".rst", ".md")

    # Muster für Überschriften
    CHAPTER_PATTERNS = [
        re.compile(r'^(KAPITEL|CHAPTER|TEIL|PART|ABSCHNITT|SECTION)\s+[\dIVXivx]+', re.I),
        re.compile(r'^[\dIVXivx]+\.\s+[A-ZÄÖÜ\d].{5,80}$'),
        re.compile(r'^#{1,4}\s+\S'),          # Bereits Markdown-Headings
        re.compile(r'^[A-ZÄÖÜ][A-ZÄÖÜ\s]{4,60}$'),  # ALLES GROSSBUCHSTABEN
    ]

    def convert(self, input_path: Path) -> Document:
        content = input_path.read_text(encoding="utf-8", errors="replace")

        # RST oder Markdown bereits vorhanden → direkt nutzbar
        if input_path.suffix == ".md":
            return self._from_markdown(content, input_path)

        meta = self._make_meta(input_path, input_path.suffix.upper().lstrip("."))
        doc  = Document(meta=meta)

        lines   = content.splitlines()
        chapter = doc.add_chapter("Inhalt")
        para_buf: list[str] = []

        def flush_para():
            text = " ".join(para_buf).strip()
            if text:
                chapter.blocks.append(Block(type=BlockType.PARAGRAPH, text=text))
            para_buf.clear()

        for line in lines:
            stripped = line.strip()

            if not stripped:
                flush_para()
                continue

            # Heading-Erkennung
            level = self._detect_heading_level(stripped, lines)
            if level:
                flush_para()
                if level == 1:
                    chapter = doc.add_chapter(stripped.lstrip("#").strip())
                    doc.meta.chapters = len(doc.chapters)
                else:
                    btype = {2: BlockType.HEADING_2, 3: BlockType.HEADING_3,
                             4: BlockType.HEADING_4}.get(level, BlockType.HEADING_4)
                    chapter.blocks.append(Block(type=btype, text=stripped.lstrip("#").strip()))
                continue

            # Listen-Erkennung
            list_m = re.match(r'^([-*•·]|\d+[.)]) +(.+)', stripped)
            if list_m:
                flush_para()
                is_ordered = bool(re.match(r'^\d', list_m.group(1)))
                chapter.blocks.append(Block(
                    type=BlockType.LIST_ITEM,
                    text=list_m.group(2).strip(),
                    ordered=is_ordered,
                ))
                continue

            # Normaler Text → Absatz-Buffer
            para_buf.append(stripped)

        flush_para()
        return doc

    def _detect_heading_level(self, line: str, all_lines: list[str]) -> int:
        # Markdown-Headings
        m = re.match(r'^(#{1,4})\s+', line)
        if m:
            return len(m.group(1))

        # Chapter-Pattern
        for pat in self.CHAPTER_PATTERNS:
            if pat.match(line):
                return 1

        # Kurze Zeile (< 60 Zeichen) nach einer Leerzeile → potentielle Überschrift
        stripped = line.rstrip()
        if (len(stripped) < 60
                and not stripped.endswith(('.', ',', ';', ':', '?', '!'))
                and stripped[0].isupper()):
            return 2

        return 0

    def _from_markdown(self, content: str, path: Path) -> Document:
        """Bereits Markdown → YAML-Frontmatter ergänzen + Kapitel strukturieren."""
        meta = self._make_meta(path, "Markdown")
        doc  = Document(meta=meta)

        chapter = doc.add_chapter("Inhalt")
        for line in content.splitlines():
            m = re.match(r'^(#{1,4})\s+(.*)', line)
            if m:
                level, text = len(m.group(1)), m.group(2).strip()
                if level == 1:
                    chapter = doc.add_chapter(text)
                    doc.meta.chapters = len(doc.chapters)
                else:
                    btype = {2: BlockType.HEADING_2, 3: BlockType.HEADING_3,
                             4: BlockType.HEADING_4}.get(level, BlockType.HEADING_4)
                    chapter.blocks.append(Block(type=btype, text=text))
            elif line.strip():
                chapter.blocks.append(Block(type=BlockType.PARAGRAPH, text=line.strip()))

        return doc
