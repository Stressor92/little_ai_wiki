from __future__ import annotations

from tools.shared import lineage_validator, metadata_validator, reference_validator, size_validator
from tools.shared.validation_rules import VALIDATOR_ORDER, get_validation_options


_REGISTRY = {
    "lineage": lineage_validator.validate_transition,
    "metadata": metadata_validator.validate_transition,
    "references": reference_validator.validate_transition,
    "size": size_validator.validate_transition,
}


def get_transition_validators(config: dict) -> list[tuple[str, callable]]:
    opts = get_validation_options(config)
    enabled_map = {
        "lineage": opts.get("validate_lineage", True),
        "metadata": opts.get("validate_metadata", True),
        "references": opts.get("validate_references", True),
        "size": opts.get("validate_sizes", True),
    }

    out: list[tuple[str, callable]] = []
    for name in VALIDATOR_ORDER:
        if enabled_map.get(name, True):
            out.append((name, _REGISTRY[name]))
    return out
