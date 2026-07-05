"""
converters/html_utils.py
Shared HTML → Block-Liste Parser (BeautifulSoup-basiert).
Wird von EPUB, HTML und Calibre-Converter genutzt.
"""

from __future__ import annotations
import re
from typing import Optional

from .base import Block, BlockType

# Tags die als Überschriften behandelt werden
HEADING_MAP = {
    "h1": BlockType.HEADING_1,
    "h2": BlockType.HEADING_2,
    "h3": BlockType.HEADING_3,
    "h4": BlockType.HEADING_4,
    "h5": BlockType.HEADING_4,
    "h6": BlockType.HEADING_4,
}


def html_to_blocks(html_content: str) -> list[Block]:
    """
    Konvertiert HTML-String zu einer geordneten Liste von Blocks.
    Unterstützt: Headings, Paragraphen, Listen, Tabellen,
                 Blockquotes, Code, <hr>
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("beautifulsoup4 fehlt: pip install beautifulsoup4 lxml")

    soup = BeautifulSoup(html_content, "lxml")

    # body extrahieren wenn vorhanden
    body = soup.find("body") or soup

    # Navigations-/Metadaten-Tags entfernen
    for tag in body.find_all(["nav", "aside", "footer", "header", "script", "style"]):
        tag.decompose()

    blocks: list[Block] = []
    _process_node(body, blocks, list_level=0, ordered=False)
    return _merge_paragraphs(blocks)


def _process_node(node, blocks: list[Block], list_level: int, ordered: bool) -> None:
    """Rekursiv alle Kindelemente verarbeiten."""
    from bs4 import NavigableString, Tag

    for child in node.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text and text not in ("\n", "\r\n"):
                # Loose Text im body → Paragraph
                if blocks and blocks[-1].type == BlockType.PARAGRAPH:
                    blocks[-1].text += " " + text
                elif text:
                    blocks.append(Block(type=BlockType.PARAGRAPH, text=text))
            continue

        if not isinstance(child, Tag):
            continue

        tag = child.name.lower() if child.name else ""

        # Headings
        if tag in HEADING_MAP:
            text = _get_text(child)
            if text:
                blocks.append(Block(type=HEADING_MAP[tag], text=text))

        # Paragraphen
        elif tag == "p":
            text = _get_rich_text(child)
            if text:
                blocks.append(Block(type=BlockType.PARAGRAPH, text=text))

        # Ungeordnete Listen
        elif tag == "ul":
            for li in child.find_all("li", recursive=False):
                text = _get_rich_text(li)
                if text:
                    blocks.append(Block(
                        type=BlockType.LIST_ITEM,
                        text=text,
                        level=list_level,
                        ordered=False,
                    ))
                # Verschachtelte Listen
                for sub_ul in li.find_all(["ul", "ol"], recursive=False):
                    _process_node(sub_ul, blocks,
                                  list_level=list_level + 1,
                                  ordered=sub_ul.name == "ol")

        # Geordnete Listen
        elif tag == "ol":
            for idx, li in enumerate(child.find_all("li", recursive=False), 1):
                text = _get_rich_text(li)
                if text:
                    blocks.append(Block(
                        type=BlockType.LIST_ITEM,
                        text=text,
                        level=list_level,
                        ordered=idx,
                    ))
                for sub_ul in li.find_all(["ul", "ol"], recursive=False):
                    _process_node(sub_ul, blocks,
                                  list_level=list_level + 1,
                                  ordered=sub_ul.name == "ol")

        # Blockquote
        elif tag == "blockquote":
            text = _get_rich_text(child)
            if text:
                blocks.append(Block(type=BlockType.QUOTE, text=text))

        # Code-Blöcke
        elif tag in ("pre", "code"):
            text = child.get_text()
            if text.strip():
                blocks.append(Block(type=BlockType.CODE, text=text))

        # Horizontale Linie
        elif tag == "hr":
            blocks.append(Block(type=BlockType.DIVIDER, text=""))

        # Tabellen
        elif tag == "table":
            _process_table(child, blocks)

        # Bild-Beschriftung
        elif tag in ("figcaption", "caption"):
            text = _get_text(child)
            if text:
                blocks.append(Block(type=BlockType.CAPTION, text=text))

        # div/section/article → rekursiv
        elif tag in ("div", "section", "article", "main", "figure",
                     "aside", "chapter", "epigraph"):
            _process_node(child, blocks, list_level, ordered)

        # span, em, strong als Teil von Loose-Text
        elif tag in ("span", "em", "strong", "b", "i", "a"):
            text = _get_rich_text(child)
            if text:
                if blocks and blocks[-1].type == BlockType.PARAGRAPH:
                    blocks[-1].text += " " + text
                else:
                    blocks.append(Block(type=BlockType.PARAGRAPH, text=text))

        # br → Zeilenumbruch im letzten Block
        elif tag == "br":
            if blocks and blocks[-1].type == BlockType.PARAGRAPH:
                blocks[-1].text += "\n"

        else:
            # Unbekannte Tags → Kinder verarbeiten
            _process_node(child, blocks, list_level, ordered)


def _process_table(table_node, blocks: list[Block]) -> None:
    """Verarbeitet eine HTML-Tabelle in TABLE_HEADER + TABLE_ROW Blocks."""
    # Header-Zeilen (thead > tr > th)
    thead = table_node.find("thead")
    if thead:
        for tr in thead.find_all("tr"):
            cells = [_get_text(td) for td in tr.find_all(["th", "td"])]
            if any(cells):
                blocks.append(Block(type=BlockType.TABLE_HEADER, cells=cells, text=""))
    else:
        # Erste Zeile mit <th> als Header
        first_row = table_node.find("tr")
        if first_row and first_row.find("th"):
            cells = [_get_text(td) for td in first_row.find_all(["th", "td"])]
            blocks.append(Block(type=BlockType.TABLE_HEADER, cells=cells, text=""))

    # Datenzeilen
    tbody = table_node.find("tbody") or table_node
    for tr in tbody.find_all("tr"):
        # Überspringen wenn schon als Header verarbeitet
        if tr.find("th") and not thead:
            continue
        cells = [_get_text(td) for td in tr.find_all(["td", "th"])]
        if any(cells):
            blocks.append(Block(type=BlockType.TABLE_ROW, cells=cells, text=""))


def _get_text(tag) -> str:
    """Extrahiert reinen Text aus einem BS4-Tag."""
    return " ".join(tag.get_text(separator=" ").split()).strip()


def _get_rich_text(tag) -> str:
    """
    Extrahiert Text mit Markdown-Inline-Formatierung.
    bold → **text**, italic → *text*, code → `text`
    """
    from bs4 import NavigableString, Tag
    parts = []

    for child in tag.descendants:
        if isinstance(child, NavigableString):
            text = str(child)
            if text.strip():
                parent_tags = {p.name for p in child.parents if isinstance(p, Tag)}
                # Nur wenn direktes Kind, nicht in tiefer verschachtelten Tags
                if not parent_tags.intersection({"ul", "ol", "table", "pre", "code"}):
                    # Inline-Formatierung anwenden
                    if "strong" in parent_tags or "b" in parent_tags:
                        text = f"**{text.strip()}**"
                    elif "em" in parent_tags or "i" in parent_tags:
                        text = f"*{text.strip()}*"
                    elif "code" in parent_tags:
                        text = f"`{text.strip()}`"
                    parts.append(text.strip())

    result = " ".join(parts)
    # Mehrfache Leerzeichen normalisieren
    result = re.sub(r'\s+', ' ', result).strip()
    return result


def _merge_paragraphs(blocks: list[Block]) -> list[Block]:
    """
    Fügt aufeinanderfolgende kurze Paragraph-Fragmente zusammen,
    trennt aber logische Absätze (leere Blöcke, nach Headings).
    """
    if not blocks:
        return blocks

    merged = []
    for block in blocks:
        if (block.type == BlockType.PARAGRAPH
                and merged
                and merged[-1].type == BlockType.PARAGRAPH
                and len(merged[-1].text) < 200
                and not merged[-1].text.endswith(('.', '!', '?', ':', '"', '»'))):
            merged[-1].text += " " + block.text
        else:
            merged.append(block)

    return merged
