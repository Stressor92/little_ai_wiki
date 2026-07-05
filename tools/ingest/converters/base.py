"""
converters/base.py
Gemeinsame Datenstrukturen und Markdown-Writer für alle Converter.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
import re


# ─── Dokumentstruktur ────────────────────────────────────────────────────────

class BlockType(Enum):
    HEADING_1    = "h1"
    HEADING_2    = "h2"
    HEADING_3    = "h3"
    HEADING_4    = "h4"
    PARAGRAPH    = "p"
    CODE         = "code"
    QUOTE        = "quote"
    LIST_ITEM    = "li"
    TABLE_ROW    = "tr"
    TABLE_HEADER = "th"
    DIVIDER      = "hr"
    CAPTION      = "caption"
    EMPTY        = "empty"


@dataclass
class Block:
    type:    BlockType
    text:    str
    level:   int = 0           # Für verschachtelte Listen
    ordered: bool = False      # Für geordnete Listen
    cells:   list[str] = field(default_factory=list)  # Für Tabellen


@dataclass
class Chapter:
    title:    str
    blocks:   list[Block] = field(default_factory=list)
    number:   int = 0


@dataclass
class DocumentMeta:
    title:      str = ""
    author:     str = ""
    publisher:  str = ""
    date:       str = ""
    language:   str = ""
    description:str = ""
    source_file:str = ""
    source_fmt: str = ""
    converted:  str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    pages:      int = 0
    chapters:   int = 0
    isbn:       str = ""


@dataclass
class Document:
    meta:     DocumentMeta
    chapters: list[Chapter] = field(default_factory=list)

    def add_chapter(self, title: str) -> Chapter:
        ch = Chapter(title=title, number=len(self.chapters) + 1)
        self.chapters.append(ch)
        return ch

    def current_chapter(self) -> Chapter:
        if not self.chapters:
            self.add_chapter("Inhalt")
        return self.chapters[-1]


# ─── Markdown-Writer ─────────────────────────────────────────────────────────

class MarkdownWriter:
    """Konvertiert ein Document-Objekt in strukturiertes Markdown."""

    def __init__(self, add_toc: bool = True, add_frontmatter: bool = True):
        self.add_toc         = add_toc
        self.add_frontmatter = add_frontmatter

    def write(self, doc: Document, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = self.render(doc)
        output_path.write_text(content, encoding="utf-8")

    def render(self, doc: Document) -> str:
        parts = []

        if self.add_frontmatter:
            parts.append(self._frontmatter(doc.meta))

        if self.add_toc and len(doc.chapters) > 2:
            parts.append(self._toc(doc))

        for ch in doc.chapters:
            parts.append(self._chapter(ch))

        return "\n\n".join(parts).strip() + "\n"

    # ── Abschnitte ───────────────────────────────────────────────────────────

    def _frontmatter(self, m: DocumentMeta) -> str:
        lines = ["---"]
        if m.title:       lines.append(f'title: "{self._escape_yaml(m.title)}"')
        if m.author:      lines.append(f'author: "{self._escape_yaml(m.author)}"')
        if m.publisher:   lines.append(f'publisher: "{self._escape_yaml(m.publisher)}"')
        if m.date:        lines.append(f'date: "{m.date}"')
        if m.language:    lines.append(f'language: "{m.language}"')
        if m.isbn:        lines.append(f'isbn: "{m.isbn}"')
        if m.pages:       lines.append(f'pages: {m.pages}')
        if m.chapters:    lines.append(f'chapters: {m.chapters}')
        lines.append(f'source_file: "{m.source_file}"')
        lines.append(f'source_format: "{m.source_fmt}"')
        lines.append(f'converted: "{m.converted}"')
        if m.description: lines.append(f'description: >\n  {m.description[:300]}')
        lines.append("---")
        return "\n".join(lines)

    def _toc(self, doc: Document) -> str:
        lines = ["## Inhaltsverzeichnis\n"]
        for i, ch in enumerate(doc.chapters, 1):
            slug = self._slug(ch.title)
            lines.append(f"{i}. [{ch.title}](#{slug})")
        return "\n".join(lines)

    def _chapter(self, ch: Chapter) -> str:
        parts = []
        if ch.title:
            parts.append(f"# {ch.title}")

        table_buffer: list[Block] = []

        for block in ch.blocks:
            # Tabellen puffern bis Tabellenende
            if block.type in (BlockType.TABLE_HEADER, BlockType.TABLE_ROW):
                table_buffer.append(block)
                continue
            if table_buffer:
                parts.append(self._table(table_buffer))
                table_buffer.clear()

            rendered = self._block(block)
            if rendered:
                parts.append(rendered)

        if table_buffer:
            parts.append(self._table(table_buffer))

        return "\n\n".join(parts)

    # ── Blöcke ───────────────────────────────────────────────────────────────

    def _block(self, b: Block) -> str:
        t = self._clean(b.text)
        match b.type:
            case BlockType.HEADING_1: return f"# {t}"
            case BlockType.HEADING_2: return f"## {t}"
            case BlockType.HEADING_3: return f"### {t}"
            case BlockType.HEADING_4: return f"#### {t}"
            case BlockType.PARAGRAPH: return t
            case BlockType.QUOTE:     return "\n".join(f"> {l}" for l in t.splitlines())
            case BlockType.CODE:      return f"```\n{b.text}\n```"
            case BlockType.DIVIDER:   return "---"
            case BlockType.CAPTION:   return f"*{t}*"
            case BlockType.LIST_ITEM:
                indent = "  " * b.level
                prefix = f"{b.ordered}." if isinstance(b.ordered, int) else "-"
                return f"{indent}{prefix} {t}"
            case _:                   return ""

    def _table(self, rows: list[Block]) -> str:
        if not rows:
            return ""
        headers = [b for b in rows if b.type == BlockType.TABLE_HEADER]
        data    = [b for b in rows if b.type == BlockType.TABLE_ROW]

        if not headers and not data:
            return ""

        # Spaltenanzahl ermitteln
        all_rows = headers + data
        n_cols = max((len(r.cells) for r in all_rows), default=1)

        lines = []
        if headers:
            header_row = headers[0]
            cells = [self._clean(c) for c in header_row.cells]
            cells += [""] * (n_cols - len(cells))
            lines.append("| " + " | ".join(cells) + " |")
            lines.append("| " + " | ".join(["---"] * n_cols) + " |")
        else:
            # Erste Datenzeile als Header
            first = data[0].cells
            cells = [self._clean(c) for c in first]
            cells += [""] * (n_cols - len(cells))
            lines.append("| " + " | ".join(cells) + " |")
            lines.append("| " + " | ".join(["---"] * n_cols) + " |")
            data = data[1:]

        for row in data:
            cells = [self._clean(c) for c in row.cells]
            cells += [""] * (n_cols - len(cells))
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)

    # ── Hilfsmethoden ────────────────────────────────────────────────────────

    @staticmethod
    def _clean(text: str) -> str:
        if not text:
            return ""
        # Mehrfache Leerzeichen/Newlines normalisieren
        text = re.sub(r'\r\n|\r', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.strip()
        # Pipe in Tabellen escapen
        text = text.replace("|", "\\|")
        return text

    @staticmethod
    def _escape_yaml(text: str) -> str:
        return text.replace('"', '\\"').replace('\n', ' ')

    @staticmethod
    def _slug(text: str) -> str:
        slug = text.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        return slug.strip('-')


# ─── Basis-Converter ─────────────────────────────────────────────────────────

class BaseConverter:
    """Abstrakte Basis-Klasse für alle Format-Converter."""

    SUPPORTED_EXTENSIONS: tuple[str, ...] = ()

    def convert(self, input_path: Path) -> Document:
        raise NotImplementedError

    @staticmethod
    def supports(path: Path) -> bool:
        raise NotImplementedError

    @staticmethod
    def _make_meta(path: Path, fmt: str) -> DocumentMeta:
        return DocumentMeta(
            title=path.stem.replace("_", " ").replace("-", " ").title(),
            source_file=path.name,
            source_fmt=fmt,
        )
