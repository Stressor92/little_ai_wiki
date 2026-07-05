from __future__ import annotations

import time

from tools.shared.validation_result import ValidatorResult
from tools.shared.validation_rules import TRANSITION_LAYER_MAP, normalize_required_keys
from tools.shared.utils import normalize_meta_value


def _validate_record_fields(result: ValidatorResult, record: dict, required: tuple[str, ...], layer: int) -> None:
    file = str(record.get("__file", ""))
    for field in required:
        value = normalize_meta_value(record, field)
        if not value:
            result.add_message(
                identifier=field,
                file=file,
                rule=f"metadata_layer_{layer}",
                description=f"missing required field '{field}'",
                severity="ERROR",
            )


def validate_transition(transition: str, artifacts: dict, config: dict) -> ValidatorResult:
    start = time.monotonic()
    result = ValidatorResult(validator="metadata")

    from_layer, to_layer = TRANSITION_LAYER_MAP[transition]
    required_from = normalize_required_keys(from_layer)
    required_to = normalize_required_keys(to_layer)

    from_records: list[dict] = artifacts.get("from_records", [])
    to_records: list[dict] = artifacts.get("to_records", [])

    for rec in from_records:
        result.checked += 1
        _validate_record_fields(result, rec, required_from, from_layer)

    for rec in to_records:
        result.checked += 1
        _validate_record_fields(result, rec, required_to, to_layer)

    result.duration = round(time.monotonic() - start, 6)
    return result
