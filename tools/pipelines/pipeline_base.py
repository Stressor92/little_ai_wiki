from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

from tools.pipelines.pipeline_context import PipelineContext
from tools.pipelines.pipeline_registry import get_stage_registry, resolve_stage_order
from tools.pipelines.pipeline_report import PipelineReport, StageReport, write_pipeline_report
from tools.pipelines.pipeline_validator import validate_post_execution, validate_pre_execution
from tools.pipelines.stage_executor import StageExecutionError, execute_stage
from tools.pipelines.utils import path_checksum, stable_execution_id
from tools.shared.validators import validate_transition, should_block_pipeline


EXIT_SUCCESS = 0
EXIT_VALIDATION = 1
EXIT_STAGE_FAILURE = 2
EXIT_CONFIG = 3
EXIT_INTERRUPT = 4


@dataclass
class PipelineRunResult:
    exit_code: int
    report: PipelineReport


def _stage_inputs(context: PipelineContext, stage: str) -> Path:
    root = context.workspace_root
    domain = context.domain
    mapping = {
        "discover_sources": context.input_path,
        "ingest": context.input_path,
        "chapter_splitter": root / f"10_md_{domain}",
        "chunk_builder": root / f"20_chapter_{domain}",
        "evidence_index": root / f"30_chunk_{domain}",
        "embedding_builder": root / f"40_index_{domain}",
        "wiki_builder": root / f"40_index_{domain}",
        "analysis_builder": root / f"60_wiki_{domain}",
    }
    return mapping[stage]


def _stage_outputs(context: PipelineContext, stage: str) -> Path:
    root = context.workspace_root
    domain = context.domain
    mapping = {
        "discover_sources": root / f"00_raw_{domain}",
        "ingest": root / f"10_md_{domain}",
        "chapter_splitter": root / f"20_chapter_{domain}",
        "chunk_builder": root / f"30_chunk_{domain}",
        "evidence_index": root / f"40_index_{domain}",
        "embedding_builder": root / f"50_embedding_{domain}",
        "wiki_builder": root / f"60_wiki_{domain}",
        "analysis_builder": root / f"80_{domain}_analysis",
    }
    return mapping[stage]


def _transition_for_stage(stage_name: str) -> str | None:
    mapping = {
        "chapter_splitter": "10_to_20",
        "chunk_builder": "20_to_30",
        "evidence_index": "30_to_40",
        "embedding_builder": "40_to_50",
    }
    return mapping.get(stage_name)


def _transition_paths(context: PipelineContext, transition: str) -> tuple[Path, Path]:
    root = context.workspace_root
    d = context.domain
    mapping = {
        "10_to_20": (root / f"10_md_{d}", root / f"20_chapter_{d}"),
        "20_to_30": (root / f"20_chapter_{d}", root / f"30_chunk_{d}"),
        "30_to_40": (root / f"30_chunk_{d}", root / f"40_index_{d}"),
        "40_to_50": (root / f"40_index_{d}", root / f"50_embedding_{d}"),
    }
    return mapping[transition]


def _state_file(context: PipelineContext) -> Path:
    return context.output_path / ".pipeline_state" / f"{context.pipeline}_{context.domain}.json"


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _stage_signature(context: PipelineContext, stage: str, version: str) -> dict[str, str]:
    inp = _stage_inputs(context, stage)
    out = _stage_outputs(context, stage)
    cfg_hash = stable_execution_id(stage, context.domain, context.configuration)
    return {
        "input_checksum": path_checksum(inp),
        "output_checksum": path_checksum(out),
        "config_checksum": cfg_hash,
        "version": version,
    }


def run_pipeline(context: PipelineContext, mode: str) -> PipelineRunResult:
    registry = get_stage_registry()
    pre = validate_pre_execution(context, registry)

    report = PipelineReport(
        run_id=context.execution_id,
        pipeline=mode,
        domain=context.domain,
        configuration=context.configuration,
    )

    if not pre.ok:
        report.status = "failed"
        report.add_stage(StageReport(stage="pre_validation", status="failed", errors=pre.errors, warnings=pre.warnings))
        write_pipeline_report(report, context.report_path)
        return PipelineRunResult(exit_code=EXIT_VALIDATION, report=report)

    order = resolve_stage_order(registry)
    state_path = _state_file(context)
    prior_state = _load_state(state_path)
    next_state: dict[str, Any] = {}

    upstream_changed = False

    try:
        for stage_name in order:
            stage = registry[stage_name]
            signature = _stage_signature(context, stage_name, stage.version)
            previous_sig = prior_state.get(stage_name)

            should_run = mode == "full"
            if mode == "incremental":
                if previous_sig != signature:
                    should_run = True
                elif upstream_changed:
                    should_run = True
                else:
                    should_run = False

            if not should_run:
                sr = StageReport(stage=stage_name, status="skipped", skipped=1)
                report.add_stage(sr)
                next_state[stage_name] = signature
                continue

            result = execute_stage(stage_name, stage.runner, context)
            sr = StageReport(
                stage=stage_name,
                status=result.status,
                created=result.created,
                updated=result.updated,
                skipped=result.skipped,
                warnings=result.warnings,
                errors=result.errors,
                duration=result.duration,
                artifacts=result.artifacts,
            )
            report.add_stage(sr)

            if result.status in {"failed", "error"} or result.errors:
                report.status = "failed"
                write_pipeline_report(report, context.report_path)
                return PipelineRunResult(exit_code=EXIT_STAGE_FAILURE, report=report)

            transition = _transition_for_stage(stage_name)
            if transition is not None:
                from_path, to_path = _transition_paths(context, transition)
                transition_result = validate_transition(
                    transition=transition,
                    from_path=from_path,
                    to_path=to_path,
                    config=context.configuration,
                )
                report.validation[transition] = transition_result.to_dict()

                if should_block_pipeline(transition_result, context.configuration):
                    report.status = "failed"
                    report.add_stage(
                        StageReport(
                            stage=f"validation_{transition}",
                            status="failed",
                            errors=["transition validation failed"],
                        )
                    )
                    write_pipeline_report(report, context.report_path)
                    return PipelineRunResult(exit_code=EXIT_VALIDATION, report=report)

                if transition_result.warning_count() > 0:
                    report.add_stage(
                        StageReport(
                            stage=f"validation_{transition}",
                            status="warning",
                            warnings=["transition validation emitted warnings"],
                        )
                    )
                else:
                    report.add_stage(
                        StageReport(
                            stage=f"validation_{transition}",
                            status="completed",
                        )
                    )

            current_sig = _stage_signature(context, stage_name, stage.version)
            next_state[stage_name] = current_sig

            if mode == "incremental":
                upstream_changed = previous_sig != current_sig

    except KeyboardInterrupt:
        report.status = "failed"
        report.add_stage(StageReport(stage="interruption", status="failed", errors=["user interruption"]))
        write_pipeline_report(report, context.report_path)
        return PipelineRunResult(exit_code=EXIT_INTERRUPT, report=report)
    except StageExecutionError as exc:
        report.status = "failed"
        report.add_stage(StageReport(stage="stage_executor", status="failed", errors=[str(exc)]))
        write_pipeline_report(report, context.report_path)
        return PipelineRunResult(exit_code=EXIT_STAGE_FAILURE, report=report)

    _save_state(state_path, next_state)
    write_pipeline_report(report, context.report_path)

    post = validate_post_execution(context, report)
    if not post.ok:
        report.status = "failed"
        report.add_stage(StageReport(stage="post_validation", status="failed", errors=post.errors, warnings=post.warnings))
        write_pipeline_report(report, context.report_path)
        return PipelineRunResult(exit_code=EXIT_VALIDATION, report=report)

    if post.warnings:
        report.add_stage(StageReport(stage="post_validation", status="warning", warnings=post.warnings))
        write_pipeline_report(report, context.report_path)

    return PipelineRunResult(exit_code=EXIT_SUCCESS, report=report)
