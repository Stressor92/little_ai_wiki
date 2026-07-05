from __future__ import annotations

import time
from pathlib import Path

from tools.shared.utils import load_layer_records
from tools.shared.validation_registry import get_transition_validators
from tools.shared.validation_result import TransitionValidationReport
from tools.shared.validation_rules import TRANSITION_LAYER_MAP, get_validation_options


def _collect_transition_artifacts(transition: str, from_path: Path, to_path: Path) -> dict:
    from_layer, to_layer = TRANSITION_LAYER_MAP[transition]
    return {
        "layers": (from_layer, to_layer),
        "from_path": from_path,
        "to_path": to_path,
        "from_records": load_layer_records(from_layer, from_path),
        "to_records": load_layer_records(to_layer, to_path),
    }


def validate_transition(transition: str, from_path: Path, to_path: Path, config: dict) -> TransitionValidationReport:
    if transition not in TRANSITION_LAYER_MAP:
        raise ValueError(f"unsupported transition: {transition}")

    opts = get_validation_options(config)
    report = TransitionValidationReport(transition=transition)

    if not opts.get("enabled", True):
        return report

    artifacts = _collect_transition_artifacts(transition, from_path, to_path)

    for _, validator in get_transition_validators(config):
        started = time.monotonic()
        result = validator(transition, artifacts, config)
        result.duration = round(time.monotonic() - started, 6)
        report.add_validator_result(result)

    if opts.get("fail_on_warning", False):
        has_warning = any(v.severity == "WARNING" for v in report.validators.values())
        if has_warning and report.status != "failed":
            report.status = "failed"

    return report


def should_block_pipeline(transition_report: TransitionValidationReport, config: dict) -> bool:
    opts = get_validation_options(config)
    if transition_report.has_fatal():
        return True
    if transition_report.has_errors() and opts.get("stop_on_error", True):
        return True
    if opts.get("fail_on_warning", False) and transition_report.warning_count() > 0:
        return True
    return False
