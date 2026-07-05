from __future__ import annotations

from pathlib import Path
import json

from tools.structure.utils import parse_frontmatter


def deterministic_md_files(path: Path) -> list[Path]:
    files = [p for p in path.rglob("*.md") if p.is_file()]
    return sorted(files, key=lambda p: p.as_posix().lower())


def load_frontmatter_record(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    parsed = parse_frontmatter(raw)
    meta = dict(parsed.metadata)
    meta["__file"] = path.as_posix()
    meta["__body"] = parsed.body
    return meta


def load_layer_records(layer: int, path: Path) -> list[dict]:
    if layer in {10, 20, 30}:
        records: list[dict] = []
        for file in deterministic_md_files(path):
            if file.name == "INDEX.md" or file.name.lower().endswith("_toc.md"):
                continue
            try:
                records.append(load_frontmatter_record(file))
            except Exception:
                records.append({"__file": file.as_posix(), "__load_error": True})
        records.sort(key=lambda r: str(r.get("__file", "")))
        return records

    if layer == 40:
        index_json = path / "index.json" if path.is_dir() else path
        if not index_json.exists():
            return []
        try:
            data = json.loads(index_json.read_text(encoding="utf-8"))
            if isinstance(data, list):
                out = []
                for item in data:
                    if isinstance(item, dict):
                        rec = dict(item)
                        rec["__file"] = index_json.as_posix()
                        out.append(rec)
                out.sort(key=lambda r: (str(r.get("evidence_id", "")), str(r.get("chunk_id", ""))))
                return out
        except Exception:
            return [{"__file": index_json.as_posix(), "__load_error": True}]
        return []

    if layer == 50:
        embeddings_json = path / "embeddings.json" if path.is_dir() else path
        if not embeddings_json.exists():
            return []
        try:
            data = json.loads(embeddings_json.read_text(encoding="utf-8"))
            if isinstance(data, list):
                out = []
                for item in data:
                    if isinstance(item, dict):
                        rec = dict(item)
                        rec["__file"] = embeddings_json.as_posix()
                        out.append(rec)
                out.sort(key=lambda r: (str(r.get("embedding_id", "")), str(r.get("chunk_id", ""))))
                return out
        except Exception:
            return [{"__file": embeddings_json.as_posix(), "__load_error": True}]
        return []

    return []


def normalize_meta_value(record: dict, key: str) -> str:
    aliases = {
        "hash": ("hash", "source_hash", "hash_sha256"),
        "lineage": ("lineage", "lineage_path"),
        "chapter_id": ("chapter_id", "chapter"),
        "heading": ("heading", "title", "chapter_heading"),
        "sequence": ("sequence", "chapter"),
        "confidence": ("confidence", "score"),
        "source_references": ("source_references", "lineage", "lineage_path", "source_file"),
    }
    candidates = aliases.get(key, (key,))
    for c in candidates:
        if c in record and record[c] not in (None, ""):
            return str(record[c])
    return ""


def parse_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default
