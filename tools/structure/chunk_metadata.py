from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.structure.utils import slugify, sha256_text


@dataclass(frozen=True)
class ChunkMetadata:
    values: dict[str, Any]


def _normalize_chapter_id(raw: str) -> str:
    txt = str(raw).strip()
    if txt.isdigit():
        return f"ch{int(txt):02d}"
    return slugify(txt)


def build_chunk_metadata(
    *,
    chapter_meta: dict[str, str],
    chunk_content: str,
    domain: str,
    topic: str,
    chapter_file: Path,
    sequence: int,
    token_count: int,
    paragraph_start: int,
    paragraph_end: int,
    created_at: str,
    updated_at: str,
) -> ChunkMetadata:
    document_id = chapter_meta.get("document_id") or slugify(chapter_file.parent.name + "_" + chapter_file.stem)
    chapter_id_raw = chapter_meta.get("chapter_id") or chapter_meta.get("chapter") or chapter_file.stem
    chapter_id = _normalize_chapter_id(chapter_id_raw)

    chunk_id = f"chunk_{document_id}_{chapter_id}_{sequence:04d}"
    chapter_heading = chapter_meta.get("title") or chapter_meta.get("chapter_heading") or chapter_file.stem

    lineage = {
        "layer20_file": chapter_meta.get("layer20_file") or chapter_file.as_posix(),
        "layer10_document": chapter_meta.get("layer10_document") or chapter_meta.get("source_file", ""),
        "layer00_source": chapter_meta.get("layer00_source") or chapter_meta.get("lineage_path") or chapter_meta.get("source_file", ""),
        "chapter_heading": chapter_heading,
        "paragraph_start": paragraph_start,
        "paragraph_end": paragraph_end,
    }

    values: dict[str, Any] = {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "chapter_id": chapter_id,
        "source_id": chapter_meta.get("source_id", ""),
        "domain": chapter_meta.get("domain") or domain,
        "topic": chapter_meta.get("topic") or topic,
        "sequence": sequence,
        "token_count": token_count,
        "source_file": chapter_meta.get("source_file") or chapter_file.name,
        "created_at": chapter_meta.get("created_at") or created_at,
        "updated_at": updated_at,
        "hash_sha256": sha256_text(chunk_content),
        "lineage": lineage,
    }

    for optional_key in ("language", "author", "tags"):
        if chapter_meta.get(optional_key):
            values[optional_key] = chapter_meta[optional_key]

    return ChunkMetadata(values=values)
