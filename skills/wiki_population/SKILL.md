# Wiki Population

## Purpose

Populate and maintain a domain knowledge wiki using only verified evidence from the knowledge pipeline.

The goal is to create a comprehensive, internally linked and evidence-based wiki that faithfully represents the available knowledge without introducing unsupported information.

---

## Inputs

Primary sources

* `10_md_<domain>`
* `20_chapter_<domain>`
* `30_chunk_<domain>`
* `40_index_<domain>`
* `50_embedding_<domain>`

Existing wiki

* `60_wiki_<domain>/`
* `60_wiki_<domain>/INDEX.md`

---

## Workflow

1. Read and understand `INDEX.md`.
2. Scan the existing wiki structure.
3. Read evidence from the Evidence Index.
4. Use semantic retrieval to collect relevant chunks for each wiki page.
5. Verify every statement against indexed evidence.
6. Update existing pages or create missing pages.
7. Add internal references to related wiki pages.
8. Split oversized pages into hierarchical subpages.
9. Update navigation and cross references.
10. Report all created and modified pages.

---

## Rules

### Evidence First

* Every factual statement must be supported by evidence.
* Every statement must be traceable to one or more evidence records.
* Never generate unsupported knowledge.
* Never invent facts.
* Contradictory evidence must be documented instead of resolved by assumption.

---

### Evidence Sources

Use only

* normalized documents
* chapters
* chunks
* evidence index
* semantic retrieval

Never use

* model memory
* external knowledge
* assumptions
* speculation

---

### Internal Linking

Every page should reference

* parent topics
* child topics
* related topics
* prerequisite concepts
* broader categories

Cross references should create a navigable knowledge graph.

Avoid isolated pages.

---

### Hierarchical Growth

If a page becomes too large

* identify coherent subtopics
* create dedicated child pages
* move detailed content into child pages
* leave concise summaries on the parent page
* link both directions

Example

```text
machine_learning.md

├── supervised_learning.md

├── unsupervised_learning.md

├── reinforcement_learning.md

└── neural_networks.md
```

Parent pages remain overview pages.

Child pages contain detailed knowledge.

---

### Writing Rules

Every page should

* explain one topic
* remain logically structured
* use deterministic headings
* avoid duplication
* prefer concise summaries with links to detailed pages

Do not repeat identical knowledge across multiple pages.

---

### Evidence References

Every major section should reference

* evidence IDs
* source documents
* supporting chunks

Evidence must remain traceable through the pipeline.

---

### Contradictions

If conflicting evidence exists

* document all positions
* reference all supporting evidence
* never remove conflicting evidence
* clearly identify uncertainty

---

### Semantic Retrieval

Embeddings may be used only for

* discovering relevant chunks
* identifying related pages
* finding semantically similar concepts

Embeddings never replace evidence.

---

### Existing Pages

Before editing

* read the complete page
* preserve valid content
* preserve existing links
* extend instead of rewriting

Do not delete verified knowledge automatically.

---

### Page Organization

Each page should contain

* short introduction
* key concepts
* detailed sections
* related topics
* evidence references
* further reading inside the wiki

---

### Navigation

Maintain

* parent links
* child links
* sibling links
* topic indexes
* category pages

Navigation should remain deterministic.

---

### Naming

Use

* lowercase
* snake_case
* stable filenames

One topic per page.

---

### Quality Rules

Every page must

* contain only verified information
* reference evidence
* contain internal links
* fit into the wiki hierarchy
* remain readable
* avoid duplicate content

---

## Success Criteria

* Every populated page is fully evidence-based.
* Every factual statement is traceable through the Evidence Index.
* Related wiki pages are interconnected through internal links.
* Large topics are automatically decomposed into hierarchical subpages.
* Parent pages provide concise overviews and link to detailed child pages.
* Contradictory evidence is documented transparently.
* No unsupported knowledge is introduced.
* Existing verified content is preserved and only extended where appropriate.
* The complete wiki forms a coherent, navigable knowledge graph built exclusively from the repository's pipeline artifacts.
