from __future__ import annotations

import re
import time
import math

from tools.shared.validation_result import ValidatorResult
from tools.shared.validation_rules import get_size_limits
from tools.shared.utils import normalize_meta_value, parse_int


def _token_count_from_body(rec: dict) -> int:
    body = str(rec.get("__body", ""))
    return len(re.findall(r"\S+", body))


def validate_transition(transition: str, artifacts: dict, config: dict) -> ValidatorResult:
    start = time.monotonic()
    result = ValidatorResult(validator="size")

    _, to_layer = artifacts.get("layers", (0, 0))
    to_records: list[dict] = artifacts.get("to_records", [])
    min_tokens, max_tokens = get_size_limits(config)

    expected_vector_dim: int | None = None
    expected_model_version: str | None = None

    for rec in to_records:
        result.checked += 1
        file = str(rec.get("__file", ""))

        if to_layer == 20:
            tokens = _token_count_from_body(rec)
            if tokens <= 0:
                result.add_message(identifier=file, file=file, rule="size_chapter_non_empty", description="chapter body is empty", severity="ERROR")

        elif to_layer == 30:
            token_count = parse_int(normalize_meta_value(rec, "token_count"), default=_token_count_from_body(rec))
            if token_count < min_tokens:
                result.add_message(identifier=normalize_meta_value(rec, "chunk_id") or file, file=file, rule="size_chunk_min", description=f"chunk below minimum token threshold ({token_count} < {min_tokens})", severity="WARNING")
            if token_count > max_tokens:
                result.add_message(identifier=normalize_meta_value(rec, "chunk_id") or file, file=file, rule="size_chunk_max", description=f"chunk above maximum token threshold ({token_count} > {max_tokens})", severity="ERROR")

        elif to_layer == 40:
            preview = str(rec.get("content_preview", ""))
            if len(preview.strip()) == 0:
                result.add_message(identifier=normalize_meta_value(rec, "evidence_id") or file, file=file, rule="size_evidence_content", description="evidence preview empty", severity="WARNING")

        elif to_layer == 50:
            embedding_id = normalize_meta_value(rec, "embedding_id") or file
            model_version = normalize_meta_value(rec, "model_version")
            vector = rec.get("vector")

            if not model_version:
                result.add_message(identifier=embedding_id, file=file, rule="embedding_model_version", description="model_version missing", severity="ERROR")
            elif expected_model_version is None:
                expected_model_version = model_version
            elif model_version != expected_model_version:
                result.add_message(
                    identifier=embedding_id,
                    file=file,
                    rule="embedding_model_version_consistency",
                    description=f"inconsistent model_version '{model_version}' (expected '{expected_model_version}')",
                    severity="ERROR",
                )

            if not isinstance(vector, list):
                result.add_message(identifier=embedding_id, file=file, rule="embedding_vector_type", description="vector is not a list", severity="ERROR")
                continue

            if len(vector) == 0:
                result.add_message(identifier=embedding_id, file=file, rule="embedding_vector_non_empty", description="vector is empty", severity="ERROR")
            elif expected_vector_dim is None:
                expected_vector_dim = len(vector)
            elif len(vector) != expected_vector_dim:
                result.add_message(
                    identifier=embedding_id,
                    file=file,
                    rule="embedding_vector_dimension_consistency",
                    description=f"inconsistent vector dimension {len(vector)} (expected {expected_vector_dim})",
                    severity="ERROR",
                )

            for idx, val in enumerate(vector):
                if not isinstance(val, (int, float)):
                    result.add_message(
                        identifier=embedding_id,
                        file=file,
                        rule="embedding_vector_numeric",
                        description=f"vector element at index {idx} is not numeric",
                        severity="ERROR",
                    )
                    break
                if not math.isfinite(float(val)):
                    result.add_message(
                        identifier=embedding_id,
                        file=file,
                        rule="embedding_vector_finite",
                        description=f"vector element at index {idx} is not finite",
                        severity="ERROR",
                    )
                    break

    result.duration = round(time.monotonic() - start, 6)
    return result
