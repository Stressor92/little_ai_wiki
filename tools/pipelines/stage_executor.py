from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools.pipelines.pipeline_report import ALLOWED_STATUS_VALUES


@dataclass
class StageResult:
    status: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    duration: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class StageExecutionError(RuntimeError):
    pass


def validate_stage_result(result: StageResult) -> None:
    if result.status not in ALLOWED_STATUS_VALUES:
        raise StageExecutionError(f"invalid stage result status: {result.status}")


def execute_stage(stage_name: str, runner, context) -> StageResult:
    try:
        result = runner(context)
    except KeyboardInterrupt as exc:
        raise
    except Exception as exc:  # noqa: BLE001
        raise StageExecutionError(f"stage {stage_name} execution failed: {exc}") from exc

    if not isinstance(result, StageResult):
        raise StageExecutionError(f"stage {stage_name} returned non-StageResult")
    validate_stage_result(result)
    return result
