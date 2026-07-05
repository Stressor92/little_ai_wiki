# Modular Knowledge Pipeline

This repository provides a generic, domain-agnostic wiki pipeline.
It turns raw source material into traceable markdown, chunks, evidence indexes,
embeddings, wiki pages, and analysis outputs.

It is designed as a Retrieval-Augmented Generation (RAG) foundation to help you build your own AI wiki for your specific needs, inspired by [### LLM Wiki - Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## Canonical Rule

If documentation conflicts, [AGENTS.md](AGENTS.md) is the source of truth.

## What This Wiki Can Do

- Build the same layered knowledge structure for any domain.
- Keep full lineage from source files to downstream claims.
- Support retrieval-oriented workflows via chunk + index + embedding layers.
- Support AI and human workflows with shared folder and ID contracts.
- Run deterministic full and incremental pipelines from stable CLI entrypoints.

## What This Wiki Cannot Do (Limitations)

- It does not guarantee truth by itself; outputs still depend on source quality.
- It does not replace evidence review; claims must stay citation-backed.
- It does not allow skipping lineage metadata between layers.
- It does not support arbitrary folder naming outside canonical layer patterns.
- It does not automatically resolve domain-specific legal/medical correctness.

## Layer Structure

- `00_raw_<domain>`
- `10_md_<domain>`
- `20_chapter_<domain>`
- `30_chunk_<domain>`
- `40_index_<domain>`
- `50_embedding_<domain>`
- `60_wiki_<domain>`
- `70_personal_<domain>_data`
- `80_<domain>_analysis`
- `90_<domain>_skills`
- `personas`
- `tools`

## Quick Start: Create a New Wiki Domain

The easiest way is to use the bootstrap tool.

### 1) Create the domain skeleton

```powershell
python -m tools.bootstrap.bootstrap --domain template --topic example_project --report template_bootstrap_report.json
```

This generates all canonical layer folders plus `INDEX.md` files.

### 2) Add source material

Put initial files into:

- `00_raw_template/`

Include provenance metadata (for example source URL, date, license, hash).

### 3) Run the full pipeline

```powershell
python -m tools.pipelines.pipeline_full --domain template --input 00_raw_template --output . --report pipeline_full_template.json
```

### 4) Run incremental updates later

```powershell
python -m tools.pipelines.pipeline_incremental --domain template --input 00_raw_template --output . --report pipeline_incremental_template.json
```

## Suggested First-Run Workflow for Humans

1. Bootstrap one domain (example: `template`).
2. Add a very small source set (1 to 3 files).
3. Run `pipeline_full` once.
4. Inspect layer outputs and lineage consistency.
5. Add more sources, then use `pipeline_incremental`.

## Testing New Raw Sources (Template Example)

Use ingest first to validate source conversion before running the full pipeline.

### Dry-run format validation

```powershell
python -m tools.ingest.pipeline_ingest --domain template --input 00_raw_template/source1 --output 10_md_template --recursive --dry-run --report source1_ingest_dryrun_report.json
```

### Real conversion run

```powershell
python -m tools.ingest.pipeline_ingest --domain template --input 00_raw_template/source1 --output 10_md_template --recursive --report source1_ingest_report.json
```

Practical support in the current toolchain includes:

- PDF, EPUB, DOCX, DOC, ODT
- PPTX, HTML/HTM/XHTML, XML
- CSV, XLSX/XLS
- TXT, MD, RST, MOBI

Notes:

- Legacy `.doc` conversion prefers LibreOffice (`soffice`) and falls back to Windows Word COM (`pywin32`) when available.
- Ingest output names are collision-safe for files that share the same stem but have different extensions.

## Retrieval From SQLite Embeddings

When embedding data grows, prefer SQLite retrieval over loading one large JSON file.

Example:

```powershell
python -m tools.retrieval.embedding_search_sqlite --domain template --query "lorem ipsum" --top-k 5 --report 50_embedding_template/retrieval_template_report.json
```

Optional filters:

- `--topic <topic>` to constrain results.
- `--input <path-to-embeddings.db>` to use a custom database path.
- `--index <path-to-index.json>` to enrich results with previews and lineage fields.

## Root Files

- [AGENTS.md](AGENTS.md)
- [README.md](README.md)
- [requirements.txt](requirements.txt)