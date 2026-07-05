"""
converters/pdf_conv.py
PDF → Markdown via PyMuPDF (fitz)

Struktur-Erkennung:
  - Fontgröße → Überschrift-Ebene (Top-N Größen = h1/h2/h3)
  - Fettdruck + Kapitalgröße → Subheading
  - Blöcke → Absätze
  - Tabellen via pdfplumber (falls installiert)
  - Kopf-/Fußzeilen werden erkannt und gefiltert
"""

from __future__ import annotations
import re
import logging
from collections import Counter
from pathlib import Path
from typing import Optional

from .base import (
    BaseConverter, Block, BlockType, Chapter,
    Document, DocumentMeta,
)

log = logging.getLogger(__name__)


class PDFConverter(BaseConverter):
    SUPPORTED_EXTENSIONS = (".pdf",)

    # Zeilen unter dieser Länge als Überschrift-Kandidaten behandeln
    MAX_HEADING_LEN = 120

    def convert(self, input_path: Path) -> Document:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDF fehlt: pip install pymupdf")

        doc_fitz = fitz.open(str(input_path))
        meta     = self._extract_meta(doc_fitz, input_path)
        doc      = Document(meta=meta)

        # Schriftgrößen analysieren → Überschrift-Schwellenwerte ermitteln
        font_sizes   = self._collect_font_sizes(doc_fitz)
        thresholds   = self._heading_thresholds(font_sizes)
        header_footer_y = self._detect_header_footer_zones(doc_fitz)

        current_chapter: Optional[Chapter] = None
        list_state: dict = {}

        for page_num, page in enumerate(doc_fitz):
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

            for block in blocks:
                if block["type"] != 0:   # 0 = Text, 1 = Image
                    continue

                block_y = block["bbox"][1]
                # Kopf-/Fußzeile überspringen
                if self._in_header_footer(block_y, page.rect.height, header_footer_y):
                    continue

                for line in block["lines"]:
                    line_text = ""
                    max_size  = 0.0
                    is_bold   = False
                    is_italic = False

                    for span in line["spans"]:
                        line_text += span["text"]
                        size       = span["size"]
                        flags      = span["flags"]
                        if size > max_size:
                            max_size = size
                        if flags & 2 ** 4:   # bold flag
                            is_bold = True
                        if flags & 2 ** 1:   # italic flag
                            is_italic = True

                    line_text = line_text.strip()
                    if not line_text:
                        continue

                    # Seitenzahl-Pattern überspringen
                    if re.match(r'^[\d\s]+$', line_text) and len(line_text) < 8:
                        continue

                    # Überschrift bestimmen
                    heading_level = self._classify_heading(
                        line_text, max_size, is_bold, thresholds
                    )

                    if heading_level == 1:
                        # Neues Kapitel
                        current_chapter = doc.add_chapter(line_text)
                        doc.meta.chapters = len(doc.chapters)

                    elif heading_level in (2, 3, 4):
                        ch = current_chapter or doc.current_chapter()
                        btype = {2: BlockType.HEADING_2,
                                 3: BlockType.HEADING_3,
                                 4: BlockType.HEADING_4}[heading_level]
                        ch.blocks.append(Block(type=btype, text=line_text))

                    else:
                        # Normaler Absatz — List-Erkennung
                        ch = current_chapter or doc.current_chapter()

                        list_match = re.match(
                            r'^(?:[-•·▪▸★◆]\s+|(\d+)[.)]\s+)(.+)', line_text
                        )
                        if list_match:
                            ordered = bool(list_match.group(1))
                            item_text = list_match.group(2) or list_match.group(0)
                            ch.blocks.append(Block(
                                type=BlockType.LIST_ITEM,
                                text=item_text,
                                ordered=ordered,
                            ))
                        elif is_italic and len(line_text) < 200:
                            ch.blocks.append(Block(
                                type=BlockType.CAPTION,
                                text=line_text,
                            ))
                        else:
                            # An letzten Absatz anhängen oder neuen starten
                            if (ch.blocks
                                    and ch.blocks[-1].type == BlockType.PARAGRAPH
                                    and not line_text.endswith(('.', '!', '?', ':', '"'))):
                                ch.blocks[-1].text += " " + line_text
                            else:
                                ch.blocks.append(Block(
                                    type=BlockType.PARAGRAPH,
                                    text=line_text,
                                ))

        meta.pages = doc_fitz.page_count
        doc_fitz.close()

        # Versuche, Tabellen mit pdfplumber zu extrahieren (optional)
        self._try_extract_tables(input_path, doc)

        return doc

    # ── Metadaten ─────────────────────────────────────────────────────────────

    def _extract_meta(self, doc_fitz, path: Path) -> DocumentMeta:
        m = doc_fitz.metadata or {}
        return DocumentMeta(
            title       = m.get("title")    or path.stem,
            author      = m.get("author")   or "",
            date        = m.get("creationDate", "")[:10],
            source_file = path.name,
            source_fmt  = "PDF",
            pages       = doc_fitz.page_count,
        )

    # ── Font-Analyse ──────────────────────────────────────────────────────────

    def _collect_font_sizes(self, doc_fitz) -> Counter:
        sizes: Counter = Counter()
        sample = min(doc_fitz.page_count, 30)   # Erste 30 Seiten analysieren
        for i in range(sample):
            page = doc_fitz[i]
            for block in page.get_text("dict")["blocks"]:
                if block["type"] != 0:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        sz = round(span["size"], 1)
                        sizes[sz] += len(span["text"].strip())
        return sizes

    def _heading_thresholds(self, sizes: Counter) -> dict[int, float]:
        """
        Ordnet Schriftgrößen Überschrift-Levels zu.
        Logik: Top-3 häufigste Übergrößen → h1, h2, h3.
        Körpertext-Größe = die am häufigsten vorkommende.
        """
        if not sizes:
            return {1: 99, 2: 99, 3: 99}

        # Körpertext = häufigste Größe
        body_size = sizes.most_common(1)[0][0]

        # Alle Größen über Körpertext
        larger = sorted(
            [s for s in sizes if s > body_size + 0.5],
            reverse=True
        )

        thresholds: dict[int, float] = {}
        for level, size in zip([1, 2, 3], larger[:3]):
            thresholds[level] = size

        # Fallback: body + delta
        if 1 not in thresholds: thresholds[1] = body_size + 6
        if 2 not in thresholds: thresholds[2] = body_size + 3
        if 3 not in thresholds: thresholds[3] = body_size + 1

        log.debug(f"Körpertext: {body_size}pt | Thresholds: {thresholds}")
        return thresholds

    def _classify_heading(
        self,
        text: str,
        size: float,
        is_bold: bool,
        thresholds: dict[int, float],
    ) -> int:
        """Gibt Heading-Level 1-4 zurück, oder 0 für normalen Text."""
        if len(text) > self.MAX_HEADING_LEN:
            return 0

        for level in [1, 2, 3]:
            if size >= thresholds.get(level, 99):
                return level

        # Fettgedruckte kurze Zeile → H4
        if is_bold and len(text) < 80 and not text.endswith('.'):
            return 4

        return 0

    # ── Kopf-/Fußzeilen ───────────────────────────────────────────────────────

    def _detect_header_footer_zones(self, doc_fitz) -> tuple[float, float]:
        """Gibt (header_max_y, footer_min_y) als relative Werte zurück."""
        # Einfache Heuristik: Obere 7% und untere 7% der Seite
        return (0.07, 0.93)

    def _in_header_footer(
        self, y: float, page_height: float, zones: tuple[float, float]
    ) -> bool:
        rel_y = y / page_height if page_height else 0
        return rel_y < zones[0] or rel_y > zones[1]

    # ── Tabellen (optional, via pdfplumber) ───────────────────────────────────

    def _try_extract_tables(self, path: Path, doc: Document) -> None:
        try:
            import pdfplumber
        except ImportError:
            return

        try:
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables() or []:
                        if not table:
                            continue
                        ch = doc.current_chapter()
                        ch.blocks.append(Block(type=BlockType.DIVIDER, text=""))
                        header, *rows = table
                        if header:
                            ch.blocks.append(Block(
                                type=BlockType.TABLE_HEADER,
                                cells=[str(c or "") for c in header],
                                text="",
                            ))
                        for row in rows:
                            ch.blocks.append(Block(
                                type=BlockType.TABLE_ROW,
                                cells=[str(c or "") for c in row],
                                text="",
                            ))
        except Exception as e:
            log.debug(f"pdfplumber table extraction failed: {e}")
