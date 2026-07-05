from __future__ import annotations

from pathlib import Path
from typing import Any


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return "''"
    txt = str(value).replace('"', '\\"')
    return f'"{txt}"'


def _yaml_dump_map(data: dict[str, Any], indent: int = 0) -> list[str]:
    pad = " " * indent
    lines: list[str] = []
    for key in sorted(data.keys()):
        value = data[key]
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines.extend(_yaml_dump_map(value, indent + 2))
        elif isinstance(value, list):
            lines.append(f"{pad}{key}:")
            for item in value:
                lines.append(f"{pad}  - {_yaml_scalar(item)}")
        else:
            lines.append(f"{pad}{key}: {_yaml_scalar(value)}")
    return lines


def render_chunk_markdown(metadata: dict[str, Any], content: str) -> str:
    fm = "\n".join(["---", *_yaml_dump_map(metadata), "---", "", "# Chunk", "", content.strip(), ""])
    return fm


def chunk_output_path(output_root: Path, document_id: str, sequence: int, flat: bool) -> Path:
    filename = f"chunk_{sequence:04d}.md"
    if flat:
        return output_root / f"{document_id}_{filename}"
    return output_root / document_id / filename
