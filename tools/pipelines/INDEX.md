---
type: module-index
module: tools/pipelines
status: active
last_updated: "2026-06-28"
---

# Pipeline Orchestrator

## Entrypoints
- Full: `python -m tools.pipelines.pipeline_full`
- Incremental: `python -m tools.pipelines.pipeline_incremental`

## Shared CLI Contract
- `--domain` (required)
- `--input`
- `--output`
- `--dry-run`
- `--force`
- `--report`
- `--config`
- `--workers`
- `--verbose`

## Exit Codes
- `0` success
- `1` validation failure
- `2` stage execution failure
- `3` configuration error
- `4` user interruption

## Stage Registry (Canonical Order)
1. discover_sources
2. ingest
3. chapter_splitter
4. chunk_builder
5. evidence_index
6. embedding_builder
7. wiki_builder
8. analysis_builder

## Core Modules
- `pipeline_base.py`: run loop, incremental state, deterministic report writing.
- `pipeline_registry.py`: stage definitions, dependency graph, order resolution.
- `pipeline_runner.py`: stage adapters that invoke dedicated processing modules.
- `pipeline_context.py`: immutable execution context.
- `pipeline_report.py`: standardized JSON report schema.
- `pipeline_validator.py`: pre/post pipeline validation.
- `stage_executor.py`: StageResult contract and stage execution guardrails.
- `utils.py`: shared CLI/config/checksum helpers.
- `source_change_detector.py`: deterministic SHA256 source-change detection and machine-readable reports for incremental gating.

## Incremental Precheck
Incremental mode now executes source change detection before stage execution.

Workflow:
1. Detect changes in `00_raw_<domain>` against previous manifest.
2. If no changes and no `--force`: stop with success status.
3. If changes exist: execute incremental pipeline.
4. Persist new source manifest only after successful run.
