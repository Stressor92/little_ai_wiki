# Knowledge Pipeline Runner
skill: rag_pipeline

## Purpose

Keep one domain pipeline synchronized with newly added source documents.

## Trigger

Execute when

* new files are added to `00_raw_<domain>`
* existing source metadata changes
* user explicitly requests a pipeline run

## Workflow

1. Execute the repository tool that detects changed source files.
2. If no changes are detected:

   * stop execution
   * report "No new raw files."
3. If changes are detected:

   * execute the Incremental Pipeline for the affected domain.
4. Process stages in canonical order:

```text
00_raw_<domain>
↓

10_md_<domain>

↓

20_chapter_<domain>

↓

30_chunk_<domain>

↓

40_index_<domain>
```

5. Validate every transition.
6. Abort immediately on validation failure.
7. Return the pipeline report.

## Rules

* Never modify Layer 00.
* Never skip intermediate stages.
* Always use repository Python tools.
* Never perform manual document transformations.
* Execute only deterministic pipeline stages.
* Report every warning and error.

## Success Criteria

* All changed source files are processed.
* Every pipeline stage completed successfully.
* Validation passes for every layer transition.
* A machine-readable run report exists.
* No inconsistent lineage or broken references remain.
