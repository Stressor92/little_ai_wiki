from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_pre_execution(context, registry: dict) -> ValidationResult:
    res = ValidationResult()

    if not context.domain.strip():
        res.errors.append("domain is required")

    raw_dir = context.input_path
    if not raw_dir.exists():
        res.errors.append(f"input path does not exist: {raw_dir}")

    try:
        context.output_path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        res.errors.append(f"output path not writable: {context.output_path} ({exc})")

    if not registry:
        res.errors.append("stage registry is empty")

    return res


def validate_post_execution(context, report) -> ValidationResult:
    res = ValidationResult()
    if not context.report_path.exists():
        res.errors.append("report file missing after pipeline run")

    if report.to_dict().get("errors", 0) > 0:
        res.warnings.append("pipeline completed with stage errors")

    return res
