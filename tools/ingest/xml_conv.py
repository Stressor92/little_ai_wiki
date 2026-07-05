from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


HEADING_TAGS = {"title", "heading", "head", "h1", "h2", "h3", "h4", "section", "chapter"}
PARA_TAGS = {"p", "para", "paragraph", "text"}
LIST_TAGS = {"ul", "ol", "list"}
ITEM_TAGS = {"li", "item"}
TABLE_TAGS = {"table"}
ROW_TAGS = {"tr", "row"}
CELL_TAGS = {"td", "th", "cell"}


def _strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1].lower()
    return tag.lower()


def _node_text(node: ET.Element) -> str:
    text = "".join(node.itertext()).strip()
    return " ".join(text.split())


def convert_xml_to_markdown(input_path: Path) -> str:
    """Convert generic XML into deterministic markdown with structural mapping."""
    tree = ET.parse(str(input_path))
    root = tree.getroot()

    title = input_path.stem.replace("_", " ").replace("-", " ").strip()
    lines: list[str] = [f"# {title}", ""]

    def walk(node: ET.Element, depth: int = 0) -> None:
        tag = _strip_ns(node.tag)
        text = _node_text(node)

        if tag in HEADING_TAGS and text:
            level = min(4, max(2, depth + 2))
            lines.append(f"{'#' * level} {text}")
            lines.append("")
            return

        if tag in PARA_TAGS and text:
            lines.append(text)
            lines.append("")
            return

        if tag in LIST_TAGS:
            for child in node:
                child_tag = _strip_ns(child.tag)
                child_text = _node_text(child)
                if child_tag in ITEM_TAGS and child_text:
                    lines.append(f"- {child_text}")
            lines.append("")
            return

        if tag in TABLE_TAGS:
            rows: list[list[str]] = []
            for row in node.iter():
                if _strip_ns(row.tag) in ROW_TAGS:
                    cells = []
                    for cell in row:
                        if _strip_ns(cell.tag) in CELL_TAGS:
                            cells.append(_node_text(cell))
                    if cells:
                        rows.append(cells)
            if rows:
                width = max(len(r) for r in rows)
                header = rows[0] + [""] * (width - len(rows[0]))
                lines.append("| " + " | ".join(header) + " |")
                lines.append("| " + " | ".join(["---"] * width) + " |")
                for row in rows[1:]:
                    padded = row + [""] * (width - len(row))
                    lines.append("| " + " | ".join(padded) + " |")
                lines.append("")
            return

        # Preserve unknown non-empty nodes as XML block when leaf-like.
        if text and len(list(node)) == 0:
            lines.append("```xml")
            lines.append(ET.tostring(node, encoding="unicode").strip())
            lines.append("```")
            lines.append("")
            return

        for child in node:
            walk(child, depth + 1)

    walk(root)

    return "\n".join(lines).rstrip() + "\n"
