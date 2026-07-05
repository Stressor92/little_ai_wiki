from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkPart:
    text: str
    paragraph_start: int
    paragraph_end: int


@dataclass(frozen=True)
class ChunkObject:
    content: str
    paragraph_start: int
    paragraph_end: int
    token_count: int
