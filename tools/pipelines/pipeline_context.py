from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PipelineContext:
    domain: str
    input_path: Path
    output_path: Path
    dry_run: bool
    force: bool
    configuration: dict[str, Any]
    execution_id: str
    pipeline: str
    report_path: Path
    workers: int
    verbose: bool
    workspace_root: Path = field(default_factory=Path.cwd)
