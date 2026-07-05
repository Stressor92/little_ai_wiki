# Tools Gap Analysis

Last updated: 2026-07-04
Scope: tools layer only

## 1) Current Verified Status
- Canonical orchestrators exist and run through staged modules:
  - `tools/pipelines/pipeline_full.py`
  - `tools/pipelines/pipeline_incremental.py`
- Stage registry/dependency resolution is centralized:
  - `tools/pipelines/pipeline_registry.py`
  - `tools/pipelines/pipeline_base.py`
- Core deterministic stages are implemented and callable:
  - ingest: `tools/ingest/pipeline_ingest.py`
  - chapter split: `tools/structure/md_chapter_splitter.py`
  - chunking: `tools/structure/chunk_builder.py`
  - index: `tools/indexing/index_creator.py`
  - embeddings: `tools/embeddings/embeddings.py`
  - wiki: `tools/wiki/wiki_builder.py`
- Transition validation framework exists and blocks on `ERROR`/`FATAL`:
  - `tools/shared/validators.py`
  - `tools/shared/validation_registry.py`
  - `tools/shared/validation_rules.py`

## 2) Active High-Priority Gaps

1. Hardcoded domain/workspace assumptions still exist (open)
- Verified hardcoded values:
  - `tools/pipelines/pipeline_ingest.py`: `WORKSPACE_ROOT = Path("health_wiki")`
  - `tools/pipelines/main.py`: `--domain` defaults to `health`
  - `tools/retrieval/download.py`: `--domain` defaults to `health`
  - `tools/retrieval/inspect_db.py`: `--domain` defaults to `health`
- Impact:
  - breaks strict domain-agnostic contract
  - increases drift between canonical docs and runtime behavior

2. Stage contract inconsistency in wiki input wiring (open)
- Registry/base model says `wiki_builder` consumes layer 50 (`50_embedding_<domain>`):
  - `tools/pipelines/pipeline_registry.py`
  - `tools/pipelines/pipeline_base.py`
- Runner currently calls wiki stage with layer 40 (`40_index_<domain>`):
  - `tools/pipelines/pipeline_runner.py`
- Impact:
  - stage contract ambiguity
  - potential incorrect incremental change propagation/signature behavior
  - unclear canonical data dependency for wiki generation

3. Validation coverage stops at 30 -> 40 (open)
- Implemented transitions:
  - `10_to_20`
  - `20_to_30`
  - `30_to_40`
- Missing transitions for current full pipeline graph:
  - `40_to_50`
  - `50_to_60`
  - `60_to_80`
- Impact:
  - downstream stages can succeed without explicit contract validation

## 3) Medium-Priority Gaps

1. Legacy helper entrypoints still diverge from canonical pipeline contract
- `tools/pipelines/main.py` remains a health-specific legacy workflow despite shared CLI flags.
- Retrieval helpers still assume health defaults in argument parsing.

2. Embedding backend portability remains partial
- Current stage is deterministic file-based output.
- Missing optional adapter/config layer for alternative vector stores.

3. Compatibility shim lifecycle decision still open
- `tools/indexing/indexer.py` forwards to `tools/indexing/index_creator.py`.
- Decide and document deprecation window vs permanent compatibility policy.

## 4) Resolved or Largely Completed
- Subfolder migration and package import updates are in place.
- Transitional root wrappers were removed.
- Markdown normalizer v1 exists and is integrated in ingest flow.
- Canonical full/incremental orchestrator modules are present.

## 5) Recommended Execution Order
1. Resolve stage contract mismatch for wiki input (`40` vs `50`) and align registry/base/runner.
2. Remove hardcoded `health_wiki`/`health` assumptions from helper entrypoints.
3. Add transition validators for `40_to_50`, `50_to_60`, `60_to_80`.
4. Finalize policy for `indexer.py` compatibility shim.
5. Optional: add embedding backend adapter abstraction.

## 6) Definition of Done (Tools Layer)
- Full and incremental runs are domain-agnostic with no hardcoded domain/workspace names.
- Stage input/output contracts are consistent across registry, runner, and stage modules.
- Every executed transition has explicit validation with deterministic failure behavior.
- End-to-end run from `00_raw_<domain>` to `80_<domain>_analysis` is deterministic and report-backed.
- CLI contract is consistent for canonical entrypoints and clearly marked for any legacy helper behavior.
