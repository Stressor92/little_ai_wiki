from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import json
from pathlib import Path


@dataclass
class ChunkRunReport:
    created_chunks: list[str] = field(default_factory=list)
    updated_chunks: list[str] = field(default_factory=list)
    skipped_chunks: list[str] = field(default_factory=list)
    warnings: dict[str, list[str]] = field(default_factory=dict)
    errors: dict[str, list[str]] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=lambda: {
        "documents_processed": 0,
        "chapters_processed": 0,
        "chunks_created": 0,
        "average_chunk_size": 0,
        "largest_chunk": 0,
        "smallest_chunk": 0,
    })
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    execution_time: float = 0.0

    def finalize_chunk_stats(self, token_counts: list[int]) -> None:
        if not token_counts:
            self.stats["average_chunk_size"] = 0
            self.stats["largest_chunk"] = 0
            self.stats["smallest_chunk"] = 0
            return
        self.stats["average_chunk_size"] = round(sum(token_counts) / len(token_counts), 2)
        self.stats["largest_chunk"] = max(token_counts)
        self.stats["smallest_chunk"] = min(token_counts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_chunks": self.created_chunks,
            "updated_chunks": self.updated_chunks,
            "skipped_chunks": self.skipped_chunks,
            "warnings": self.warnings,
            "errors": self.errors,
            "validation": self.validation,
            "execution_time": self.execution_time,
            "documents_processed": self.stats["documents_processed"],
            "chapters_processed": self.stats["chapters_processed"],
            "chunks_created": self.stats["chunks_created"],
            "average_chunk_size": self.stats["average_chunk_size"],
            "largest_chunk": self.stats["largest_chunk"],
            "smallest_chunk": self.stats["smallest_chunk"],
        }


def write_report(path: Path, report: ChunkRunReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
