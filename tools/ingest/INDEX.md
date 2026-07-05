---
type: folder-index
folder: tools/ingest
title: Ingest Pipeline Concept
purpose: "Convert heterogeneous source formats into normalized markdown for layer 10"
status: target-design
last_updated: "2026-06-28"
---

# Ingest Pipeline Concept

## Objective
Build a deterministic, format-agnostic ingest flow that converts raw sources from layer 00 into clean markdown in layer 10 with:
- consistent frontmatter
- structural sectioning
- stable IDs and lineage
- reproducible formatting

## Scope
Input formats to support:
- PDF
- DOCX and DOCM
- PPTX (PowerPoint)
- XML (generic + domain XML dialects)
- EPUB
- MOBI
- AZW and AZW3
- HTML and XHTML
- TXT and Markdown passthrough

Output target:
- `10_md_<domain>` markdown files, one normalized document per source
- optional section files per document under a deterministic subfolder

## Canonical Ingest Stages
1. Discover
- Scan `00_raw_<domain>` for files by extension and source metadata.
- Resolve source ID, checksum, source path, and expected output path.

2. Detect and Route
- Map extension to converter backend.
- Fallback strategy for unknown or partially supported formats.

3. Extract
- Parse text and structural blocks from source.
- Capture headings, paragraphs, lists, tables, quotes, code-like blocks, figure/table captions.

4. Normalize
- Normalize whitespace, heading levels, list indentation, table markdown formatting.
- Keep semantics; no summarization or interpretation.

5. Sectionize
- Produce deterministic heading-based section boundaries.
- Keep one primary markdown file plus optional section files.

6. Enrich Metadata
- Ensure required frontmatter fields:
  - document_id
  - source_id
  - domain
  - topic
  - source_file
  - source_format
  - created_at
  - updated_at
  - hash_sha256
  - lineage.layer00_path

7. Validate
- UTF-8 validity
- non-empty content
- required frontmatter fields
- heading parseability
- deterministic output check (same input -> same output)

8. Write and Report
- Write markdown outputs to `10_md_<domain>`.
- Emit JSON report with changed/skipped/errors/warnings and per-file stats.

## Format Strategy

### PDF
- Primary: text extraction with heading heuristics from font hierarchy.
- Optional: table extraction backend for tabular blocks.
- OCR fallback for scanned pages (optional stage).

### DOCX and DOCM
- Use style map (Heading 1..n, List, Quote) to preserve structure.
- Preserve table and inline emphasis where possible.

### PPTX
- Slide-by-slide extraction:
  - slide title -> H2
  - section header -> H3
  - bullet levels -> nested lists
  - speaker notes -> quote/admonition block
- Keep slide number markers for traceability.

### XML
- Configurable tag mapping profile:
  - title tags -> headings
  - paragraph tags -> paragraphs
  - list tags -> lists
  - table tags -> markdown tables
- Unknown tags preserved as raw XML blocks in fenced sections.

### EPUB / MOBI / AZW / AZW3
- Prefer EPUB-native parsing where available.
- For MOBI/AZW family use conversion bridge to intermediate HTML/EPUB, then normalize.
- Spine/order must be preserved for chapter order.

### HTML / XHTML
- Semantic mapping h1..h6, p, ul/ol, table, blockquote, code.
- Strip navigation/chrome noise via rules.

## File and Folder Conventions
- Output file name:
  - `<source_type>_<source_identifier>.md` when available
  - fallback: `<stem_slug>.md`
- Optional section folder:
  - `<document_id>/sections/<nn>_<section_slug>.md`
- Deterministic slugging and lowercase snake_case naming.

## Required CLI Contract
`python -m tools.ingest.pipeline_ingest`

Arguments:
- `--domain` required unless `--input` is explicit
- `--input` file or folder
- `--output` root folder (default `10_md_<domain>`)
- `--formats` allowlist (`pdf,docx,pptx,xml,epub,mobi,...`)
- `--recursive`
- `--dry-run`
- `--force`
- `--with-sections`
- `--report` output JSON report path

## Integration Contracts
Upstream:
- reads from `00_raw_<domain>` and source metadata

Downstream:
- writes normalized markdown for:
  - `tools/structure/md_chapter_splitter.py`
  - future `tools/structure/chunk_builder.py`

## Quality Gates
Per-file gates:
- metadata complete
- lineage present
- markdown parseable
- no invalid heading jumps after normalization
- deterministic hash stable on second run

Run-level gates:
- total error rate below configured threshold
- no silent skips
- full report generated

## Missing Components to Implement
1. `tools/ingest/markdown_normalizer.py`
- dedicated deterministic normalization pass

2. `tools/ingest/pptx_conv.py`
- PowerPoint extractor and slide-to-markdown mapper

3. `tools/ingest/xml_conv.py`
- configurable XML-to-markdown converter profiles

4. MOBI/AZW conversion bridge hardening
- deterministic conversion path and explicit fallback behavior

5. `tools/ingest/pipeline_ingest.py` (module-local)
- unified orchestrator under ingest package

## Definition of Done
- Full ingest works for PDF, DOCX, PPTX, XML, EPUB, MOBI at minimum.
- Outputs are deterministic and valid for chapter splitting.
- Reports and validation are mandatory, machine-readable, and complete.
- No source file in layer 00 is modified.


---

type: architecture-specification
module: tools/ingest
title: Universal Ingest Pipeline Specification
status: draft
version: 1.0
owner: Knowledge Pipeline
last_updated: 2026-06-28
------------------------

# Universal Ingest Pipeline Specification

## Purpose

Build a deterministic, domain-agnostic ingest pipeline that converts heterogeneous source formats from Layer 00 into normalized Markdown documents for Layer 10 while preserving provenance, structure and reproducibility.

---

# Design Goals

## Primary Goals

* deterministic processing
* idempotent execution
* format agnostic architecture
* reproducible output
* complete lineage
* modular converter architecture
* no information loss where possible
* machine-readable reporting

## Secondary Goals

* scalable to very large document collections
* easily extendable with additional converters
* configurable through profiles
* suitable for automated pipelines
* CI/CD friendly

---

# Design Principles

## Determinism

* identical input always produces identical output
* output independent of execution time
* output independent of operating system
* stable document identifiers
* stable ordering
* stable formatting

---

## Idempotency

* repeated execution must never modify unchanged output
* unchanged files are skipped
* source files remain immutable
* overwrite only with explicit force flag

---

## Traceability

Every output document must contain complete provenance.

Required lineage:

* original source file
* source checksum
* conversion backend
* converter version
* processing timestamp
* originating domain
* document identifier

---

## Modularity

Pipeline consists of isolated stages.

Each stage

* accepts one defined input
* produces one defined output
* has no hidden side effects
* can be tested independently

---

# Pipeline Overview

```
Discover

↓

Detect

↓

Extract

↓

Normalize

↓

Sectionize

↓

Metadata

↓

Validate

↓

Write

↓

Report
```

---

# Pipeline Stages

## Stage 1 — Discover

### Responsibilities

* scan input folders
* discover supported files
* ignore unsupported files
* collect source metadata

### Input

* Layer 00 folder
* optional explicit file

### Output

Source objects containing

* path
* extension
* checksum
* filesize
* modified timestamp
* source id

---

## Stage 2 — Detect

### Responsibilities

* determine document type
* choose converter backend
* select configuration profile

### Output

Conversion task

containing

* converter
* parser profile
* expected capabilities

---

## Stage 3 — Extract

### Responsibilities

Extract raw document structure

Possible elements

* headings
* paragraphs
* lists
* tables
* images
* captions
* quotations
* code blocks
* notes
* hyperlinks

No interpretation allowed.

---

## Stage 4 — Normalize

### Responsibilities

Normalize

* whitespace
* line endings
* heading hierarchy
* markdown syntax
* table formatting
* list indentation
* code fences
* block quotes

Never

* summarize
* rewrite
* reorder semantic content

---

## Stage 5 — Sectionize

### Responsibilities

Generate deterministic sections.

Rules

* heading based
* stable ordering
* optional split files
* preserve hierarchy

Output

* master markdown
* optional section documents

---

## Stage 6 — Metadata

Generate mandatory frontmatter.

Required fields

* document_id
* source_id
* domain
* topic
* source_file
* source_format
* created_at
* updated_at
* hash_sha256
* converter
* converter_version
* lineage

Optional fields

* language
* author
* title
* publisher
* tags
* version

---

## Stage 7 — Validation

Validate

### Encoding

* UTF-8
* no invalid bytes

### Metadata

* required fields
* valid identifiers
* valid timestamps

### Structure

* heading hierarchy
* valid markdown
* non-empty document
* deterministic ordering

### Integrity

* checksum matches
* lineage complete

---

## Stage 8 — Write

Responsibilities

* create output folders
* write markdown
* write optional sections
* preserve timestamps where appropriate

Never modify Layer 00.

---

## Stage 9 — Report

Generate machine-readable report.

Report contains

* processed files
* skipped files
* errors
* warnings
* validation findings
* execution time
* statistics

---

# Supported Formats

## PDF

Extraction

* text
* headings
* tables
* captions

Optional

* OCR
* image extraction

---

## DOCX

Extract

* heading styles
* lists
* tables
* emphasis
* hyperlinks
* comments

---

## DOCM

Same as DOCX

Ignore

* VBA macros

---

## PPTX

Each slide becomes

* heading
* content
* notes

Maintain

* slide order
* slide numbers

---

## XML

Profile based conversion

Profiles define

* heading tags
* paragraph tags
* list tags
* table tags

Unknown tags

* preserve as raw XML

---

## EPUB

Extract

* spine order
* chapters
* metadata

Maintain reading order.

---

## MOBI / AZW / AZW3

Convert

↓

Intermediate HTML

↓

Markdown

Must be deterministic.

---

## HTML

Extract

* semantic headings
* paragraphs
* lists
* tables
* blockquotes
* code

Remove

* navigation
* menus
* advertisements
* scripts

---

## TXT

Simple normalization only.

---

## Markdown

Pass-through

Normalize formatting only.

---

# CLI Specification

Command

```
python -m tools.ingest.pipeline_ingest
```

Arguments

Required

* --domain

Optional

* --input
* --output
* --formats
* --recursive
* --dry-run
* --force
* --with-sections
* --report
* --workers
* --config

---

# Output Structure

```
10_md_<domain>/

document.md

document/

sections/

01_intro.md

02_methods.md

03_results.md
```

---

# File Naming

Rules

* lowercase
* snake_case
* deterministic
* filesystem safe

Preferred

```
<source>_<identifier>.md
```

Fallback

```
<slug>.md
```

---

# Validation Rules

Each document must satisfy

* valid UTF-8
* required metadata
* valid markdown
* stable hash
* heading hierarchy
* lineage complete

---

# Logging

Log levels

* DEBUG
* INFO
* WARNING
* ERROR

Every conversion step must be logged.

---

# Error Handling

Recoverable

* unsupported format
* missing metadata
* malformed XML

Fatal

* output not writable
* invalid configuration
* corrupted converter state

Pipeline continues whenever possible.

---

# JSON Report

Contains

* created_files
* updated_files
* skipped_files
* failed_files
* warnings
* errors
* validation_results
* execution_time
* converter_statistics

---

# Package Structure

```
tools/

ingest/

__init__.py

pipeline_ingest.py

discover.py

router.py

metadata.py

validator.py

report.py

markdown_normalizer.py

sectionizer.py

converters/

base.py

pdf_conv.py

docx_conv.py

pptx_conv.py

xml_conv.py

epub_conv.py

mobi_conv.py

html_conv.py

text_conv.py

utils.py
```

---

# Extension Points

Future modules

* OCR
* image extraction
* figure detection
* citation extraction
* bibliography parser
* metadata enrichment
* language detection
* duplicate detection
* checksum cache
* incremental ingest
* distributed processing

---

# Quality Gates

## Per Document

* conversion successful
* metadata complete
* markdown valid
* deterministic hash
* lineage complete

---

## Per Run

* report generated
* no silent failures
* error threshold below configured maximum
* all outputs validated

---

# Non Goals

Version 1 intentionally excludes

* summarization
* embeddings
* semantic chunking
* AI interpretation
* hallucination correction
* document ranking
* knowledge graph generation

These belong to downstream pipeline layers.

---

# Definition of Done

Implementation is complete when

* all supported formats are converted deterministically
* outputs are reproducible
* Layer 00 remains immutable
* Layer 10 markdown is valid
* reports are complete
* validation passes
* downstream tools can consume output without modification
* architecture is extensible through additional converter modules without changes to the orchestrator
* automated tests verify deterministic behavior across repeated executions
* full pipeline is suitable for unattended batch execution
* documentation covers CLI, configuration, extension points and validation rules
