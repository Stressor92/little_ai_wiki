# AGENTS

## Canonical Status
- This file is the single source of truth for architecture, naming, and agent behavior.
- If other docs conflict with this file, this file wins.
- Repository structure was verified against current folders.

## Mission
- Build and maintain a generic, domain-agnostic knowledge pipeline.
- Keep full traceability from source files to final analysis outputs.
- Prefer evidence-first outputs over opinion-first outputs.

## Core Model
- One pipeline per domain.
- Same folder pattern for every domain.
- Same IDs and lineage rules across all domains.

## Layer Map
- `00_raw_<domain>`: immutable source storage (files + provenance).
- `10_md_<domain>`: normalized markdown, structure preserved, no interpretation.
- `20_chapter_<domain>`: semantic document segmentation.
- `30_chunk_<domain>`: self-contained retrieval chunks (target 100-500 tokens).
- `40_index_<domain>`: structured evidence registry (scoring, links, contradictions).
- `50_embedding_<domain>`: vector embeddings for semantic retrieval.
- `60_wiki_<domain>`: human- and AI-readable topic knowledge.
- `70_personal_<domain>_data`: private context data for personalization.
- `80_<domain>_analysis`: domain reasoning outputs with uncertainty.
- `90_<domain>_skills`: reusable prompts, agents, reasoning patterns.
- `personas`: persona profiles and constraints.
- `tools`: automation for layer transitions and validation.

## Layer Contracts (Minimal)
- Layer 00 input: external source files/feeds; output: original files + metadata (source_url, download_date, license, hash).
- Layer 10 input: Layer 00; output: normalized markdown with structure preserved and source lineage.
- Layer 20 input: Layer 10; output: semantic sections/chapters with stable chapter IDs.
- Layer 30 input: Layer 20; output: self-contained chunks with provenance and token budget.
- Layer 40 input: Layer 30 (+ lineage); output: evidence records with scores, limitations, support/contradiction links.
- Layer 50 input: Layer 30; output: vectors with model/version/date metadata.
- Layer 60 input: Layer 40 (+ optional Layer 10 context); output: topic pages with evidence citations.
- Layer 80 input: Layers 60/40 + Layer 70 + Layer 100; output: recommendations/analysis with confidence and limits.
- Layer 90 input: domain process needs; output: reusable prompts/agents/checklists.
- `tools` input/output: deterministic layer transitions, validation, and maintenance operations.

## Naming Rules (Minimal)
- Folder pattern: `<nn>_<type>_<domain>` for domain layers, plus `personas` and `tools`.
- Use IDs consistently across layers (source_id -> document_id -> chapter_id -> chunk_id -> evidence_id).
- Use lowercase snake_case slugs for generated file names.

## Non-Negotiable Rules
- Never modify originals in Layer 0.
- Never publish claims without evidence references.
- Never skip lineage fields between layers.
- Never mix domain-specific logic into generic layer contracts.
- Never delete data without explicit archival intent.

## Processing Contracts
- Input contract and output contract must be explicit per layer.
- Keep transformations deterministic where possible.
- Fail fast on missing metadata or broken references.
- Keep naming consistent with numeric layer prefixes.

## Evidence Policy
- Score evidence with transparent rubric per domain.
- Record limitations and uncertainty for every non-trivial claim.
- Track support and contradiction links between evidence items.

## Agent Behavior
- Start from user intent, then choose the minimal required layer(s).
- For retrieval tasks: prioritize index + embeddings + chunks.
- For explanation tasks: return concise synthesis + cited evidence path.
- For personalization tasks: include persona + private context constraints.
- Keep outputs short, structured, and duplication-free.

## Token-Efficient Agent Playbook
- Prefer minimal-layer execution: only run the next required transition, not the full pipeline by default.
- Reuse canonical CLI contracts and avoid custom one-off scripts for routine domain setup.
- Read only required files and sections; avoid broad scans when folder naming is predictable.
- Keep outputs compact: findings first, then short action list, then optional detail.
- Use deterministic commands and one JSON report per run to reduce repeated explanation.
- Cache assumptions in short notes and update only deltas when continuing a task.

### Minimal New-Domain Setup Flow
1. Validate domain naming (`lowercase_snake_case`).
2. Bootstrap canonical folders and `INDEX.md` files.
3. Place initial sources in `00_raw_<domain>`.
4. Run `pipeline_full` once for baseline artifacts.
5. Switch to `pipeline_incremental` for updates.

### Canonical Example (`template`)
- Bootstrap:
	`python -m tools.bootstrap.bootstrap --domain template --topic example_project --report template_bootstrap_report.json`
- Full pipeline:
	`python -m tools.pipelines.pipeline_full --domain template --input 00_raw_template --output . --report pipeline_full_template.json`
- Incremental pipeline:
	`python -m tools.pipelines.pipeline_incremental --domain template --input 00_raw_template --output . --report pipeline_incremental_template.json`

### Raw Source Intake Test Loop (Token-Efficient)
1. Run ingest dry-run only on the target source folder.
2. Read only the JSON report (`discovered`, `changed`, `errors`, `warnings`).
3. Fix converter gaps first, not downstream pipeline stages.
4. Re-run the same dry-run command to verify deltas.
5. Execute one real ingest run after errors reach zero.

Canonical commands:
- `python -m tools.ingest.pipeline_ingest --domain <domain> --input 00_raw_<domain>/<source_folder> --output 10_md_<domain> --recursive --dry-run --report ingest_dryrun_<domain>.json`
- `python -m tools.ingest.pipeline_ingest --domain <domain> --input 00_raw_<domain>/<source_folder> --output 10_md_<domain> --recursive --report ingest_run_<domain>.json`

## Pipeline Orchestration (Canonical)
- Canonical entrypoints are `python -m tools.pipelines.pipeline_full` and `python -m tools.pipelines.pipeline_incremental`.
- Stage execution order is resolved from centralized registry/dependencies, not hardcoded in entrypoint modules.
- Shared stage interface is `run(context) -> StageResult`.
- Pipeline CLI contract is identical across full/incremental modes: `--domain --input --output --dry-run --force --report --config --workers --verbose`.
- Exit codes are canonical: `0` success, `1` validation failure, `2` stage execution failure, `3` configuration error, `4` user interruption.
- Each run must produce exactly one machine-readable JSON report.
- Cross-layer transition validation is mandatory for `10_to_20`, `20_to_30`, and `30_to_40` through `tools.shared.validators`.

## Generic Workflow
1. Ingest source into `00_raw_<domain>` with metadata and hash.
2. Convert to markdown in `10_md_<domain>`.
3. Segment into `20_chapter_<domain>`.
4. Chunk into `30_chunk_<domain>`.
5. Build `40_index_<domain>`.
6. Generate `50_embedding_<domain>` vectors.
7. Publish topic pages in `60_wiki_<domain>`.
8. Produce decision outputs in `80_<domain>_analysis`.

## Quality Gate
- Provenance complete.
- IDs consistent.
- Chunk sizes valid.
- Scores reproducible.
- Citations resolvable.
- Terminology consistent.

## Resolved Inconsistencies (Current Canonical)
- `40_index_*` is Layer 40 (index), `50_embedding_*` is Layer 50 (embeddings).
- Analysis layer is `80_*_analysis` (not Layer 7 paths at root naming level).
- Persona root is `personas`.
- Tool root is `tools` (not `99_tools`).

## Required Repository Updates
- Replace all stale references for legacy persona roots with `personas`.
- Replace all stale references `99_tools` -> `tools`.
- Normalize any doc text that mixes Layer 7/8 naming with folder prefixes; keep folder truth as canonical.
- Normalize any doc text that swaps index/embedding numbering; keep `40_index_*` and `50_embedding_*`.
- Remove references to deleted root docs after cleanup.
- Update command examples so script paths resolve from repository root.
- Ensure every layer/domain `INDEX.md` aligns to this file's naming and lineage rules.

## Keep/Delete Policy
- Keep at root: `AGENTS.md`, `README.md`, `requirements.txt`.
- Keep domain/layer operational `INDEX.md` files under layer folders.
- Remove redundant root concept/spec duplicates once absorbed here.