from __future__ import annotations

import re


_TOKEN_RE = re.compile(r"\S+")


def count_tokens(text: str) -> int:
    """Deterministic v1 token approximation: whitespace tokenization."""
    if not text.strip():
        return 0
    return len(_TOKEN_RE.findall(text))
