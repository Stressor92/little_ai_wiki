# Wiki Structure Builder

## Purpose

Create or extend the directory and page structure of a domain knowledge wiki based on analyzed source material.

The goal is to establish a logical, hierarchical topic structure before any knowledge pages are populated.

---

## Inputs

- `10_md_<domain>`
- `20_chapter_<domain>`
- `60_wiki_<domain>/INDEX.md` (if present)

---

## Workflow

1. Check whether `60_wiki_<domain>` already exists.
2. If an `INDEX.md` exists:
   - Read and understand the documented wiki concept.
   - Preserve the existing architecture where possible.
3. Analyze all available normalized documents and chapter files.
4. Identify the major knowledge domains and topic hierarchy.
5. Design a deterministic folder and page structure.
6. Create missing folders and empty `.md` topic pages.
7. Update `INDEX.md` to reflect the complete target structure.
8. Report all created and modified files.

---

## Rules

- `INDEX.md` is the authoritative specification of the wiki structure.
- Always read `INDEX.md` before making structural changes.
- Update `INDEX.md` whenever the structure changes.
- Preserve existing structures whenever possible.
- Extend instead of reorganizing existing hierarchies unless a major structural flaw is detected.
- Create only structural placeholder pages.
- Do not generate knowledge content.
- Do not summarize source documents.
- Use deterministic lowercase snake_case names.
- Create one topic per markdown file.
- Organize topics hierarchically.
- Avoid duplicate or overlapping topics.

---

## Structure Principles

The structure should

- begin with broad subject areas
- decompose into increasingly specific topics
- minimize overlap
- maximize discoverability
- remain extensible
- remain stable over future pipeline runs

---

## Page Creation

Create

- folders
- topic pages
- category pages
- updated `INDEX.md`

Do not create

- analysis
- summaries
- conclusions
- evidence pages

---

## INDEX.md Responsibilities

`INDEX.md` must describe

- overall wiki purpose
- structural principles
- folder hierarchy
- naming conventions
- inclusion criteria
- exclusion criteria
- relationships between major topic groups
- future extension guidelines

The INDEX must always describe the current intended structure.

---

## Existing Wiki Handling

If a wiki already exists

- preserve existing folders
- preserve existing topic pages
- identify missing topics
- identify missing parent categories
- extend the hierarchy only where required
- update `INDEX.md` accordingly

Never delete existing pages automatically.

---

## Success Criteria

- A complete high-level wiki structure exists.
- All major subject areas are represented.
- Folder hierarchy is logical and deterministic.
- Every topic has a placeholder markdown page.
- `INDEX.md` completely documents the resulting structure.
- Existing structures are preserved and only extended where appropriate.
- No knowledge content has been generated.