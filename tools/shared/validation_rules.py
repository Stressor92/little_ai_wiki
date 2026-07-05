from __future__ import annotations

REQUIRED_FIELDS_BY_LAYER = {
    10: ("document_id", "source_id", "domain", "hash", "lineage"),
    20: ("chapter_id", "document_id", "source_id", "heading", "sequence"),
    30: ("chunk_id", "chapter_id", "document_id", "token_count", "sequence"),
    40: ("evidence_id", "chunk_id", "confidence", "source_references"),
    50: ("embedding_id", "chunk_id", "evidence_id", "domain", "model_version", "vector"),
}

TRANSITION_LAYER_MAP = {
    "10_to_20": (10, 20),
    "20_to_30": (20, 30),
    "30_to_40": (30, 40),
    "40_to_50": (40, 50),
}

VALIDATOR_ORDER = (
    "lineage",
    "metadata",
    "references",
    "size",
)


def normalize_required_keys(layer: int) -> tuple[str, ...]:
    return REQUIRED_FIELDS_BY_LAYER[layer]


def get_size_limits(config: dict) -> tuple[int, int]:
    validation = config.get("validation", {}) if isinstance(config, dict) else {}
    chunk_cfg = validation.get("chunk", {}) if isinstance(validation, dict) else {}
    min_tokens = int(chunk_cfg.get("minimum_tokens", 100))
    max_tokens = int(chunk_cfg.get("maximum_tokens", 500))
    return min_tokens, max_tokens


def get_validation_options(config: dict) -> dict:
    validation = config.get("validation", {}) if isinstance(config, dict) else {}
    if not isinstance(validation, dict):
        validation = {}
    return {
        "enabled": bool(validation.get("enabled", True)),
        "stop_on_error": bool(validation.get("stop_on_error", True)),
        "fail_on_warning": bool(validation.get("fail_on_warning", False)),
        "validate_lineage": bool(validation.get("validate_lineage", True)),
        "validate_metadata": bool(validation.get("validate_metadata", True)),
        "validate_references": bool(validation.get("validate_references", True)),
        "validate_sizes": bool(validation.get("validate_sizes", True)),
    }
