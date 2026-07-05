from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_FIELDS = {
    "chunk_id",
    "document_id",
    "chapter_id",
    "source_id",
    "domain",
    "topic",
    "sequence",
    "token_count",
    "source_file",
    "created_at",
    "updated_at",
    "hash_sha256",
    "lineage",
}

REQUIRED_LINEAGE_FIELDS = {
    "layer20_file",
    "layer10_document",
    "layer00_source",
    "chapter_heading",
    "paragraph_start",
    "paragraph_end",
}


@dataclass(frozen=True)
class ChunkValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]


def validate_chunk_metadata(metadata: dict[str, Any], min_tokens: int, max_tokens: int) -> ChunkValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    missing = sorted(REQUIRED_FIELDS - set(metadata.keys()))
    if missing:
        errors.append(f"missing_fields: {', '.join(missing)}")

    lineage = metadata.get("lineage")
    if not isinstance(lineage, dict):
        errors.append("lineage is missing or not an object")
    else:
        missing_lineage = sorted(REQUIRED_LINEAGE_FIELDS - set(lineage.keys()))
        if missing_lineage:
            errors.append(f"missing_lineage_fields: {', '.join(missing_lineage)}")

    token_count = metadata.get("token_count", 0)
    if not isinstance(token_count, int):
        errors.append("token_count must be int")
    else:
        if token_count < 1:
            errors.append("token_count must be > 0")
        if token_count < min_tokens:
            warnings.append("token_count below minimum")
        if token_count > max_tokens:
            warnings.append("token_count above maximum")

    return ChunkValidationResult(valid=not errors, errors=errors, warnings=warnings)


def validate_document_ordering(chunk_metadatas: list[dict[str, Any]]) -> ChunkValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    sequences = [m.get("sequence") for m in chunk_metadatas]
    if any(not isinstance(s, int) for s in sequences):
        errors.append("sequence must be int for all chunks")
    else:
        expected = list(range(1, len(sequences) + 1))
        if sequences != expected:
            errors.append("chunk sequence ordering is not contiguous")

    starts = [m.get("lineage", {}).get("paragraph_start") for m in chunk_metadatas]
    ends = [m.get("lineage", {}).get("paragraph_end") for m in chunk_metadatas]
    for i in range(1, len(starts)):
        prev_end = ends[i - 1]
        curr_start = starts[i]
        if isinstance(prev_end, int) and isinstance(curr_start, int):
            if curr_start < prev_end:
                errors.append("overlapping paragraph ranges detected")

    return ChunkValidationResult(valid=not errors, errors=errors, warnings=warnings)
