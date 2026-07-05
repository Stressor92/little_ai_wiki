#!/usr/bin/env python3
"""
tools/retrieval/embedding_search_sqlite.py
Top-k retrieval directly from embeddings SQLite storage.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

from tools.embeddings.embeddings import _hash_vector


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SQLite embedding retrieval (top-k)")
    p.add_argument("--domain", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--input", default="", help="Path to embeddings.db")
    p.add_argument("--index", default="", help="Optional path to 40_index_<domain>/index.json")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--topic", default="", help="Optional topic filter")
    p.add_argument("--report", default="", help="Optional JSON report output")
    return p.parse_args()


def _default_db(domain: str) -> Path:
    return Path.cwd() / f"50_embedding_{domain}" / "embeddings.db"


def _default_index(domain: str) -> Path:
    return Path.cwd() / f"40_index_{domain}" / "index.json"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _load_index(index_path: Path) -> dict[str, dict[str, Any]]:
    if not index_path.exists():
        return {}
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for rec in raw:
        if not isinstance(rec, dict):
            continue
        key = str(rec.get("evidence_id", "")).strip()
        if key:
            out[key] = rec
    return out


def search_embeddings(
    *,
    db_path: Path,
    query: str,
    top_k: int,
    domain: str,
    topic: str,
    index_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    qvec = _hash_vector(query)

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        if topic:
            cur.execute(
                "SELECT embedding_id, chunk_id, evidence_id, domain, topic, model_version, vector_json, source_hash "
                "FROM embeddings WHERE domain = ? AND topic = ?",
                (domain, topic),
            )
        else:
            cur.execute(
                "SELECT embedding_id, chunk_id, evidence_id, domain, topic, model_version, vector_json, source_hash "
                "FROM embeddings WHERE domain = ?",
                (domain,),
            )

        scored: list[dict[str, Any]] = []
        for row in cur.fetchall():
            emb_id, chunk_id, evidence_id, rec_domain, rec_topic, model_version, vector_json, source_hash = row
            try:
                vec = json.loads(vector_json)
            except Exception:
                continue
            if not isinstance(vec, list):
                continue

            sim = _cosine_similarity(qvec, [float(v) for v in vec])
            idx = index_map.get(str(evidence_id), {})
            scored.append(
                {
                    "score": round(sim, 6),
                    "embedding_id": emb_id,
                    "chunk_id": chunk_id,
                    "evidence_id": evidence_id,
                    "domain": rec_domain,
                    "topic": rec_topic,
                    "model_version": model_version,
                    "source_hash": source_hash,
                    "document_id": idx.get("document_id", ""),
                    "chapter_id": idx.get("chapter_id", ""),
                    "token_count": idx.get("token_count", 0),
                    "source_file": idx.get("source_file", ""),
                    "content_preview": idx.get("content_preview", ""),
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[: max(1, top_k)]
    finally:
        conn.close()


def main() -> int:
    args = parse_args()

    db_path = Path(args.input) if args.input else _default_db(args.domain)
    index_path = Path(args.index) if args.index else _default_index(args.domain)

    if not db_path.exists():
        print(f"embeddings db not found: {db_path}")
        return 1

    index_map = _load_index(index_path)
    rows = search_embeddings(
        db_path=db_path,
        query=args.query,
        top_k=args.top_k,
        domain=args.domain,
        topic=args.topic,
        index_map=index_map,
    )

    print(f"query={args.query}")
    print(f"matches={len(rows)}")
    for i, row in enumerate(rows, start=1):
        print(f"{i:2}. score={row['score']:.4f} chunk={row['chunk_id']} topic={row['topic']}")
        if row.get("content_preview"):
            preview = str(row["content_preview"]).replace("\n", " ").strip()
            print(f"    preview={preview[:180]}")

    if args.report:
        payload = {
            "tool": "embedding_search_sqlite",
            "domain": args.domain,
            "db_path": str(db_path),
            "index_path": str(index_path),
            "query": args.query,
            "top_k": args.top_k,
            "topic": args.topic,
            "results": rows,
        }
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
