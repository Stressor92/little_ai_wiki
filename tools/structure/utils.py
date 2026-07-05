from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import re


@dataclass(frozen=True)
class FrontmatterParseResult:
    metadata: dict[str, str]
    body: str
    frontmatter_raw: str


def parse_frontmatter(text: str) -> FrontmatterParseResult:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return FrontmatterParseResult(metadata={}, body=text, frontmatter_raw="")

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return FrontmatterParseResult(metadata={}, body=text, frontmatter_raw="")

    meta: dict[str, str] = {}
    for line in lines[1:end_idx]:
        m = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", line)
        if not m:
            continue
        k = m.group(1).strip()
        v = m.group(2).strip().strip('"').strip("'")
        meta[k] = v

    body = "\n".join(lines[end_idx + 1 :]).strip("\n")
    raw = "\n".join(lines[: end_idx + 1])
    return FrontmatterParseResult(metadata=meta, body=body, frontmatter_raw=raw)


def slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in value)
    return "_".join(cleaned.split()) or "na"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def deterministic_files(input_path: Path, recursive: bool) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    pattern = "**/*.md" if recursive else "*.md"
    files = [
        p
        for p in input_path.glob(pattern)
        if p.is_file() and not p.name.lower().endswith("_toc.md")
    ]
    return sorted(files, key=lambda p: p.as_posix().lower())
