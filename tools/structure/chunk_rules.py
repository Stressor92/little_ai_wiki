from __future__ import annotations

from dataclasses import dataclass
import re

from tools.structure.chunker import ChunkObject, ChunkPart
from tools.structure.token_counter import count_tokens


@dataclass(frozen=True)
class ChunkRulesConfig:
    target_tokens: int
    minimum_tokens: int
    maximum_tokens: int
    split_tables: bool
    split_code_blocks: bool
    preserve_headings: bool


@dataclass(frozen=True)
class _Block:
    kind: str
    text: str
    idx_start: int
    idx_end: int


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_LIST_RE = re.compile(r"^(\s*[-*+]\s+|\s*\d+[.)]\s+)")
_HEADING_RE = re.compile(r"^#{1,6}\s+")


def _looks_table(line: str) -> bool:
    stripped = line.strip()
    return "|" in stripped and len(stripped) > 2


def _split_markdown_blocks(markdown: str) -> list[_Block]:
    lines = markdown.splitlines()
    blocks: list[_Block] = []
    paragraph_idx = 1
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if _HEADING_RE.match(stripped):
            blocks.append(_Block(kind="heading", text=line, idx_start=paragraph_idx, idx_end=paragraph_idx))
            i += 1
            continue

        if stripped.startswith(("```", "~~~")):
            fence = stripped[:3]
            collected = [line]
            i += 1
            while i < len(lines):
                collected.append(lines[i])
                if lines[i].strip().startswith(fence):
                    i += 1
                    break
                i += 1
            blocks.append(_Block(kind="code", text="\n".join(collected), idx_start=paragraph_idx, idx_end=paragraph_idx))
            paragraph_idx += 1
            continue

        if stripped.startswith(">"):
            collected = [line]
            i += 1
            while i < len(lines) and lines[i].strip().startswith(">"):
                collected.append(lines[i])
                i += 1
            blocks.append(_Block(kind="blockquote", text="\n".join(collected), idx_start=paragraph_idx, idx_end=paragraph_idx))
            paragraph_idx += 1
            continue

        if _looks_table(stripped):
            collected = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and _looks_table(lines[i]):
                collected.append(lines[i])
                i += 1
            blocks.append(_Block(kind="table", text="\n".join(collected), idx_start=paragraph_idx, idx_end=paragraph_idx))
            paragraph_idx += 1
            continue

        if _LIST_RE.match(line):
            collected = [line]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip():
                    break
                if _LIST_RE.match(nxt) or nxt.startswith((" ", "\t")):
                    collected.append(nxt)
                    i += 1
                    continue
                break
            blocks.append(_Block(kind="list", text="\n".join(collected), idx_start=paragraph_idx, idx_end=paragraph_idx))
            paragraph_idx += 1
            continue

        collected = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            nxt_stripped = nxt.strip()
            if not nxt_stripped:
                break
            if (
                _HEADING_RE.match(nxt_stripped)
                or nxt_stripped.startswith(("```", "~~~", ">"))
                or _LIST_RE.match(nxt)
                or _looks_table(nxt_stripped)
            ):
                break
            collected.append(nxt)
            i += 1
        blocks.append(_Block(kind="paragraph", text="\n".join(collected), idx_start=paragraph_idx, idx_end=paragraph_idx))
        paragraph_idx += 1

    return blocks


def _split_sentence_fallback(text: str, max_tokens: int, idx: int) -> list[_Block]:
    sentences = [s.strip() for s in _SENTENCE_RE.split(text.strip()) if s.strip()]
    if len(sentences) <= 1:
        return _split_whitespace_fallback(text, max_tokens, idx)

    out: list[_Block] = []
    current: list[str] = []
    current_tokens = 0
    fragment_idx = idx
    for s in sentences:
        t = count_tokens(s)
        if t > max_tokens:
            out.extend(_split_whitespace_fallback(s, max_tokens, fragment_idx))
            fragment_idx += 1
            continue
        if current_tokens + t > max_tokens and current:
            out.append(_Block(kind="paragraph", text=" ".join(current), idx_start=fragment_idx, idx_end=fragment_idx))
            fragment_idx += 1
            current = [s]
            current_tokens = t
        else:
            current.append(s)
            current_tokens += t
    if current:
        out.append(_Block(kind="paragraph", text=" ".join(current), idx_start=fragment_idx, idx_end=fragment_idx))
    return out


def _split_whitespace_fallback(text: str, max_tokens: int, idx: int) -> list[_Block]:
    words = text.split()
    out: list[_Block] = []
    start = 0
    frag_idx = idx
    while start < len(words):
        part = words[start : start + max_tokens]
        out.append(_Block(kind="paragraph", text=" ".join(part), idx_start=frag_idx, idx_end=frag_idx))
        frag_idx += 1
        start += max_tokens
    return out


def _split_oversized(block: _Block, cfg: ChunkRulesConfig) -> list[_Block]:
    tokens = count_tokens(block.text)
    if tokens <= cfg.maximum_tokens:
        return [block]

    if block.kind == "code" and not cfg.split_code_blocks:
        return [block]
    if block.kind == "table" and not cfg.split_tables:
        return [block]
    if block.kind not in {"paragraph", "list", "blockquote"}:
        return [block]

    return _split_sentence_fallback(block.text, cfg.maximum_tokens, block.idx_start)


def plan_chunks(markdown: str, cfg: ChunkRulesConfig) -> list[ChunkObject]:
    blocks = _split_markdown_blocks(markdown)
    planned: list[ChunkObject] = []

    current_parts: list[ChunkPart] = []
    current_text_parts: list[str] = []

    def _flush() -> None:
        if not current_parts:
            return
        text = "\n\n".join(part for part in current_text_parts if part.strip()).strip()
        if not text:
            return
        token_count = count_tokens(text)
        planned.append(
            ChunkObject(
                content=text + "\n",
                paragraph_start=current_parts[0].paragraph_start,
                paragraph_end=current_parts[-1].paragraph_end,
                token_count=token_count,
            )
        )

    for block in blocks:
        if block.kind == "heading" and cfg.preserve_headings:
            if current_text_parts and count_tokens("\n\n".join(current_text_parts)) >= cfg.target_tokens:
                _flush()
                current_parts = []
                current_text_parts = []
            current_parts.append(ChunkPart(text=block.text, paragraph_start=block.idx_start, paragraph_end=block.idx_end))
            current_text_parts.append(block.text)
            continue

        for piece in _split_oversized(block, cfg):
            candidate_text = "\n\n".join(current_text_parts + [piece.text]).strip()
            candidate_tokens = count_tokens(candidate_text)

            if current_text_parts and candidate_tokens > cfg.maximum_tokens:
                _flush()
                current_parts = []
                current_text_parts = []

            current_parts.append(ChunkPart(text=piece.text, paragraph_start=piece.idx_start, paragraph_end=piece.idx_end))
            current_text_parts.append(piece.text)

            current_tokens = count_tokens("\n\n".join(current_text_parts))
            if current_tokens >= cfg.target_tokens and piece.kind in {"paragraph", "list", "blockquote", "table", "code"}:
                _flush()
                current_parts = []
                current_text_parts = []

    _flush()

    return planned
