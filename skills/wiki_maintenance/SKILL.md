# Wiki Maintenance

## Purpose

Continuously validate, maintain and improve the domain knowledge wiki by comparing it against the current knowledge pipeline.

The goal is to ensure that the wiki remains complete, internally consistent, fully evidence-based and structurally healthy over time.

The skill identifies maintenance tasks but performs only deterministic and low-risk fixes automatically. Ambiguous or conflicting cases are escalated to the user.

---

## Inputs

Knowledge Pipeline

* `10_md_<domain>`
* `20_chapter_<domain>`
* `30_chunk_<domain>`
* `40_index_<domain>`
* `50_embedding_<domain>`

Wiki

* `60_wiki_<domain>/`
* `60_wiki_<domain>/INDEX.md`

---

## Workflow

1. Read `INDEX.md` and understand the intended wiki architecture.
2. Scan every wiki page.
3. Compare wiki content against the current knowledge pipeline.
4. Validate evidence, links, hierarchy and completeness.
5. Detect maintenance findings.
6. Apply safe automatic improvements where possible.
7. Escalate ambiguous findings to the user.
8. Generate or update `60_wiki_<domain>/TODO.md`.
9. Return a maintenance summary.

---

## Rules

### Preserve Existing Knowledge

* Never delete verified knowledge automatically.
* Prefer extending and correcting over rewriting.
* Preserve stable page structure.
* Preserve page history whenever possible.

---

### Link Validation

Detect

* broken internal links
* missing target pages
* orphan pages
* circular navigation
* missing parent pages
* missing child references

Automatically repair links only when the destination is unambiguous.

Otherwise create a TODO entry.

---

### Evidence Validation

Verify that every factual statement is supported by evidence.

Detect

* missing evidence references
* outdated references
* broken evidence IDs
* missing source links

If supporting evidence exists in the Evidence Index

* propose or add the reference

If no evidence exists

* flag the statement for review

---

### Completeness Validation

Compare the complete knowledge pipeline against the wiki.

Identify

* chunks not represented
* evidence never referenced
* important topics without pages
* missing sections
* missing categories

Generate TODO items for uncovered knowledge.

---

### Contradiction Detection

Identify

* conflicting evidence
* inconsistent definitions
* contradictory statements
* incompatible classifications

Do not resolve contradictions automatically.

Instead

* collect supporting evidence
* identify affected pages
* prepare a concise question for the user
* wait for explicit user decision before modifying the wiki

---

### Structural Validation

Detect

* oversized pages
* duplicate pages
* duplicate sections
* misplaced topics
* inconsistent hierarchy
* excessive nesting

Recommend structural improvements.

---

### Cross-Link Validation

Ensure

* parent pages reference children
* child pages reference parents
* related topics reference each other
* category pages remain complete

Avoid isolated knowledge.

---

### INDEX Validation

Verify that

* every documented topic exists
* every category exists
* folder hierarchy matches INDEX
* INDEX reflects the current wiki architecture

If differences exist

* update `INDEX.md`
* document structural changes

---

### TODO Generation

Maintain

```text
60_wiki_<domain>/

TODO.md
```

The file contains

* missing pages
* missing evidence
* broken links
* contradictory knowledge
* uncovered source material
* structural improvements
* user decisions required

Organize tasks by priority

```text
Critical

High

Medium

Low
```

Each task contains

* description
* affected page
* evidence reference
* recommended action

---

### Automatic Fixes

Allowed

* repair deterministic links
* add missing evidence references
* update navigation
* synchronize INDEX
* create missing placeholder pages

Not allowed

* invent facts
* remove evidence
* resolve contradictions
* rewrite large sections
* delete verified pages

---

### User Interaction

Ask the user whenever

* evidence conflicts
* multiple interpretations exist
* page restructuring is ambiguous
* duplicate pages should be merged
* unsupported statements should be removed

Questions should include

* affected pages
* supporting evidence
* conflicting evidence
* available options

---

## Success Criteria

* Every internal wiki link resolves successfully.
* Every factual statement is supported by evidence or explicitly flagged.
* All available knowledge from the pipeline is represented or tracked as a TODO.
* Contradictory information is detected and escalated to the user.
* `INDEX.md` accurately reflects the current wiki architecture.
* `TODO.md` contains all outstanding maintenance tasks, prioritized and traceable.
* The wiki remains internally consistent, fully navigable and synchronized with the current knowledge pipeline.
* No unsupported knowledge is introduced and no verified knowledge is removed automatically.
