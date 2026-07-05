---
type: architecture-specification
module: tools/pipelines/source_change_detector.py
title: Source Change Detector Specification
status: target-design
---

# Purpose
Provide a deterministic mechanism to detect whether a domain contains new or modified source documents requiring pipeline execution.

# Responsibilities
- Scan `00_raw_<domain>`
- Compute file checksums
- Compare against previous pipeline manifest
- Detect new files
- Detect modified files
- Detect removed files
- Produce deterministic change list
- Write machine-readable report

# Inputs
- domain
- optional input folder

# Outputs
- changed source files
- unchanged files
- removed files
- summary statistics

# Report Schema
- status
- changes_detected
- new_files
- modified_files
- removed_files
- unchanged_files

# Integration
Executed before `pipeline_incremental.py`.

Workflow:
1. Detect changes
2. No changes -> stop
3. Changes detected -> run incremental pipeline

# Deterministic Rules
- SHA256 based detection
- Stable file ordering
- Stable JSON reports
- No timestamp-only comparison
- Identical repository state always produces identical reports

# Definition of Done
- Detects new, modified and removed source files.
- Uses SHA256 instead of modification times.
- Produces deterministic JSON reports.
- Can be consumed directly by `pipeline_incremental.py`.
- Returns a deterministic exit status indicating whether pipeline execution is required.
