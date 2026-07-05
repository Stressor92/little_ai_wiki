from tools.bootstrap.constants import BOOTSTRAP_MARKER


def index_template(folder: str, layer_id: str, domain: str, topic: str, purpose: str):
    topic_value = topic or "general"
    return f"""{BOOTSTRAP_MARKER}
---
domain: {domain}
topic: {topic_value}
layer: {layer_id}
folder: {folder}
---

# {folder}

## Purpose

{purpose}

## Input

Artifacts from prior layer(s) or approved source inputs for this domain.

## Output

Artifacts produced by this layer, ready for validation and downstream use.

## Upstream

Primary upstream dependency: previous numbered layer in this domain workflow.

## Downstream

Primary downstream target: next numbered layer in this domain workflow.

## Quality Checklist

- Folder and file naming follow canonical conventions.
- Metadata and lineage fields are present and consistent.
- Outputs are deterministic and reproducible.
- Content is clear for both human and agent consumption.
"""


def seed_template(folder: str, seed_name: str, domain: str, topic: str):
    topic_value = topic or "general"
    title = seed_name.replace("_", " ").replace(".md", "").title()
    return f"""{BOOTSTRAP_MARKER}
---
domain: {domain}
topic: {topic_value}
folder: {folder}
seed: {seed_name}
---

# {title}

## Purpose

Bootstrap seed file for {folder}.
"""