BOOTSTRAP_MARKER = "<!-- bootstrap-generated -->"

LAYERS = [
    {
        "id": "00",
        "name": "raw",
        "folder": "00_raw_{domain}",
        "purpose": "Immutable source storage with provenance metadata.",
    },
    {
        "id": "10",
        "name": "md",
        "folder": "10_md_{domain}",
        "purpose": "Normalized markdown converted from raw sources.",
    },
    {
        "id": "20",
        "name": "chapter",
        "folder": "20_chapter_{domain}",
        "purpose": "Semantic chapter segmentation from markdown documents.",
    },
    {
        "id": "30",
        "name": "chunk",
        "folder": "30_chunk_{domain}",
        "purpose": "Self-contained retrieval chunks with stable IDs.",
    },
    {
        "id": "40",
        "name": "index",
        "folder": "40_index_{domain}",
        "purpose": "Evidence index with scoring and relationship links.",
    },
    {
        "id": "50",
        "name": "embedding",
        "folder": "50_embedding_{domain}",
        "purpose": "Vector embeddings for semantic retrieval.",
    },
    {
        "id": "60",
        "name": "wiki",
        "folder": "60_wiki_{domain}",
        "purpose": "Topic-oriented wiki pages with evidence references.",
    },
    {
        "id": "70",
        "name": "personal",
        "folder": "70_personal_{domain}_data",
        "purpose": "Private context data for personalization.",
    },
    {
        "id": "80",
        "name": "analysis",
        "folder": "80_{domain}_analysis",
        "purpose": "Evidence-backed analysis outputs and recommendations.",
    },
    {
        "id": "90",
        "name": "skills",
        "folder": "90_{domain}_skills",
        "purpose": "Reusable prompts, skills, and reasoning patterns.",
    },
]

GLOBAL_FOLDERS = ["personas", "tools"]

SEED_FILES = {
    "70": ["user_profile.md", "preferences.md"],
    "80": ["analysis_template.md"],
    "90": ["prompt_library.md", "reasoning_patterns.md"],
    "personas": ["default_persona.md"],
}

REQUIRED_SECTIONS = [
    "#",
    "## Purpose",
    "## Input",
    "## Output",
    "## Upstream",
    "## Downstream",
    "## Quality Checklist",
]


def layer_folder_name(layer: dict, domain: str) -> str:
    return layer["folder"].format(domain=domain)