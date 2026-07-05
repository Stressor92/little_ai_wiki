import re
from pathlib import Path

from tools.bootstrap.constants import LAYERS, REQUIRED_SECTIONS, layer_folder_name

DOMAIN_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_domain_name(domain):

    if not DOMAIN_PATTERN.match(domain):
        raise ValueError(
            "Domain must be lowercase snake_case."
        )


def validate_structure(root: Path, domain):

    findings = []

    expected = [layer_folder_name(layer, domain) for layer in LAYERS]

    for folder in expected:
        folder_path = root / folder
        index_path = folder_path / "INDEX.md"

        if not folder_path.exists():
            findings.append(f"Missing folder: {folder}")
            continue

        if not index_path.exists():
            findings.append(f"Missing INDEX.md: {index_path}")
            continue

        content = index_path.read_text(encoding="utf8")

        for section in REQUIRED_SECTIONS:
            if section not in content:
                findings.append(f"Missing section '{section}' in {index_path}")

    return findings