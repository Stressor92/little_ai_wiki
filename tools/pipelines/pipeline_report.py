from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json


ALLOWED_STATUS_VALUES = {
    "created",
    "updated",
    "unchanged",
    "skipped",
    "warning",
    "error",
    "failed",
    "completed",
}


@dataclass
class StageReport:
    stage: str
    status: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration: float = 0.0
    artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "warnings": self.warnings,
            "errors": self.errors,
            "duration": self.duration,
            "artifacts": self.artifacts,
        }


@dataclass
class PipelineReport:
    run_id: str
    pipeline: str
    domain: str
    configuration: dict[str, Any]
    started: str = "deterministic"
    finished: str = "deterministic"
    duration: float = 0.0
    status: str = "completed"
    stages: list[StageReport] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)

    def add_stage(self, stage: StageReport) -> None:
        if stage.status not in ALLOWED_STATUS_VALUES:
            raise ValueError(f"invalid stage status: {stage.status}")
        self.stages.append(stage)

    def summary(self) -> dict[str, int]:
        created = sum(s.created for s in self.stages)
        updated = sum(s.updated for s in self.stages)
        skipped = sum(s.skipped for s in self.stages)
        warnings = sum(len(s.warnings) for s in self.stages)
        errors = sum(len(s.errors) for s in self.stages)
        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "warnings": warnings,
            "errors": errors,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "run_id": self.run_id,
            "pipeline": self.pipeline,
            "started": self.started,
            "finished": self.finished,
            "duration": self.duration,
            "status": self.status,
            "domain": self.domain,
            "configuration": self.configuration,
            "stages": [s.to_dict() for s in self.stages],
            "validation": self.validation,
        }
        payload.update(self.summary())
        return payload


def write_pipeline_report(report: PipelineReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
