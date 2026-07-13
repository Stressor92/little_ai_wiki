---
type: folder-index
folder: tools
title: Tools Layer - Pipeline Orchestration
purpose: "Operational scripts for end-to-end domain pipeline execution"
status: active-structure-plus-target-state
last_updated: "2026-06-27"
---

# Tools - Target State Concept

## Goal
The tools folder is the execution layer for the complete pipeline:
- Create a new domain/topic structure.
- Ingest and normalize source files.
- Derive chapters and chunks.
- Build evidence index and wiki outputs.
- Generate embeddings and keep lineage consistent.

This folder should orchestrate all layer transitions, not store knowledge itself.

## Canonical Pipeline (Folder Truth)
1. `00_raw_<domain>`: ingest + provenance metadata
2. `10_md_<domain>`: normalized markdown
3. `20_chapter_<domain>`: chapter segmentation
4. `30_chunk_<domain>`: chunk generation
5. `40_index_<domain>`: evidence index
6. `50_embedding_<domain>`: vector embeddings
7. `60_wiki_<domain>`: topic wiki pages
8. `80_<domain>_analysis`: analysis outputs
9. `90_<domain>_skills`: reusable prompts/agents

Cross-cutting:
- `70_personal_<domain>_data`
- `personas`

## Current Organized Structure
1. `shared/`
- `config.py`, `database.py`, `relevance.py`, `validators.py`, `validation_registry.py`, `validation_rules.py`, `validation_result.py`, `lineage_validator.py`, `metadata_validator.py`, `reference_validator.py`, `size_validator.py`
- Shared configuration, persistence, and ranking logic.

2. `retrieval/`
- `fetchers.py`, `downloader.py`, `download.py`, `inspect_db.py`, `wiki_prepare_dump_index.py`, `wiki_download.py`, `wiki_update.py`
- Source retrieval, download handling, and DB inspection.

3. `ingest/`
- `converters/`, `pipeline_ingest.py`, `markdown_normalizer.py`, `pptx_conv.py`, `xml_conv.py`
- Raw file conversion into normalized markdown inputs.

4. `structure/`
- `md_chapter_splitter.py`, `rename_pdf.py`
- Structural preparation for chapter/chunk transitions.

5. `indexing/`
- `indexer.py`, `index_creator.py`
- Index generation and metadata-based topic indexing.

6. `embeddings/`
- `embeddings.py`
- Embedding generation and storage.

7. `wiki/`
- `wiki_builder.py`
- Wiki page generation from indexed evidence.

Stage harmonization status:
- `index_creator.py`, `embeddings.py`, and `wiki_builder.py` now share the canonical stage CLI contract (`--domain --input --output --dry-run --force --report --config --workers --verbose`).
- Stage behavior is domain-agnostic and deterministic with machine-readable stage reports.
- Cross-layer validator hooks are integrated into orchestrator transitions (`10->20`, `20->30`, `30->40`) and enforce Exit Code `1` on blocking validation findings.

8. `pipelines/`
- `pipeline_full.py`, `pipeline_incremental.py`, `pipeline_base.py`, `pipeline_registry.py`, `pipeline_runner.py`, `pipeline_context.py`, `pipeline_report.py`, `pipeline_validator.py`, `stage_executor.py`, `utils.py`
- End-to-end orchestration entry points.

9. `bootstrap/`
- Reserved for domain/topic scaffolding scripts.

## Logical Tool Modules (Target)
1. Bootstrap
- `bootstrap_domain.py`
- Create full folder skeleton for a new domain/topic.
- Create missing `INDEX.md` files from templates.

2. Ingest (00 -> 10)
- `pipeline_ingest.py`
- `converters/*`
- `rename_pdf.py`
- Convert raw formats to normalized markdown with metadata and traceability.

3. Structure (10 -> 20 -> 30)
- `md_chapter_splitter.py`
- Create chapters and retrieval chunks with stable IDs.

4. Index (30 -> 40)
- `indexer.py`
- `index_creator.py`
- Build evidence records, topic links, and quality flags.

5. Embeddings (30 -> 50)
- `embeddings.py`
- Generate and persist vectors with model/version metadata.

6. Wiki and Analysis Prep (40/50 -> 60/80)
- `wiki_builder.py`
- Build topic pages from indexed evidence.

7. Retrieval and Acquisition Helpers
- `fetchers.py`, `download.py`, `downloader.py`, `wiki_prepare_dump_index.py`, `wiki_download.py`, `wiki_update.py`, `relevance.py`
- Source retrieval and ranking support.

### Offline Wikipedia Retrieval (English)
1. Build local offline index from Wikimedia dump:
2. `python -m tools.retrieval.wiki_prepare_dump_index --domain health --input path/to/enwiki-latest-pages-articles.xml.bz2 --output 00_raw_health/wikipedia/wikipedia_index.sqlite --report 00_raw_health/wikipedia/wiki_prepare_report.json`
3. Download seed articles plus linked articles up to depth x:
4. `python -m tools.retrieval.wiki_download --domain health --input 00_raw_health/wikipedia/wikipedia_index.sqlite --output 00_raw_health/wikipedia --seeds "Diabetes mellitus,Public health" --depth 2 --max-articles 1000 --report 00_raw_health/wikipedia/wiki_download_report.json`
5. Update already populated wikipedia raw pages to latest dump revision and keep downstream layers consistent:
6. `python -m tools.retrieval.wiki_update --domain health --input 00_raw_health/wikipedia/wikipedia_index.sqlite --output 00_raw_health/wikipedia --run-pipeline incremental --report 00_raw_health/wikipedia/wiki_update_report.json`
7. Raw article format is one file per topic: `wikipedia_<slug>.txt` with YAML frontmatter metadata header + article body.
8. Legacy `wikipedia_<slug>_metadata.json` files are automatically removed by `wiki_download`/`wiki_update`.
9. Use `--dry-run` for preview, `--force` to rewrite all discovered pages, `--run-pipeline none` to skip pipeline execution.

8. Shared Runtime and Data Access
- `shared/*` and `pipelines/*`
- Configuration, persistence, and orchestration.

## Required Improvements
1. Add domain bootstrap tool
- Missing script to create complete domain structure and initial `INDEX.md` files.

2. Standardize CLI contracts
- All scripts should support: `--domain`, `--input`, `--output`, `--dry-run`, `--force`.

3. Add formatting/quality steps for markdown
- Missing dedicated markdown formatter/normalizer stage before chapter split.

4. Deterministic orchestration entry points implemented
- `pipeline_full.py`: 00 -> 80 end-to-end orchestrator.
- `pipeline_incremental.py`: dependency-aware changed-input rebuild orchestrator.
- Shared CLI contract and shared exit code mapping are enforced in common pipeline modules.

5. Add validation gates per transition
- Metadata completeness, lineage checks, ID uniqueness, token-size validation.

6. Wrapper cleanup completed
- Root wrapper scripts were removed after migration.
- Preferred execution style: `python -m tools.<module_path>`.

## Minimal Execution Paths

### A. New Domain Setup
1. Run bootstrap script.
2. Verify all `00/10/20/30/40/50/60/70/80/90/personas/tools` expectations.
3. Generate baseline `INDEX.md` files.

### B. Raw to Markdown
1. Place files in `00_raw_<domain>`.
2. Convert with ingest tools to `10_md_<domain>`.
3. Validate metadata and source references.

### C. Markdown to Chapters/Chunks
1. Split `10_md_<domain>` into `20_chapter_<domain>`.
2. Generate `30_chunk_<domain>`.
3. Validate chunk size and lineage.

### D. Index + Embeddings + Wiki
1. Build `40_index_<domain>` from chunks.
2. Build `50_embedding_<domain>` vectors.
3. Generate or refresh `60_wiki_<domain>`.

## Guardrails
- Never modify original files in `00_raw_*`.
- Never write analysis without evidence lineage.
- Never skip validation between layers.
- Keep transformations deterministic and reproducible.

## Scope Note
This file defines the target state and ordering.
Implementation details stay in each script and are tracked with concrete gaps in `tools/gap.md`.
