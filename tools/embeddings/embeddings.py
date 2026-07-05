from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


MODEL_VERSION = "hash-v1"
VECTOR_SIZE = 64


def _hash_vector(text: str, size: int = VECTOR_SIZE) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    while len(values) < size:
        for b in digest:
            values.append(round(b / 255.0, 6))
            if len(values) >= size:
                break
        digest = hashlib.sha256(digest).digest()
    return values


def _load_index(index_path: Path) -> list[dict[str, Any]]:
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
    except Exception:
        return []
    return []


def _write_sqlite(db_path: Path, embedding_records: list[dict[str, Any]]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                embedding_id TEXT PRIMARY KEY,
                chunk_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                topic TEXT NOT NULL,
                model_version TEXT NOT NULL,
                vector_json TEXT NOT NULL,
                source_hash TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_domain_topic ON embeddings(domain, topic)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_id ON embeddings(chunk_id)")

        cur.executemany(
            """
            INSERT INTO embeddings (
                embedding_id, chunk_id, evidence_id, domain, topic,
                model_version, vector_json, source_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(embedding_id) DO UPDATE SET
                chunk_id=excluded.chunk_id,
                evidence_id=excluded.evidence_id,
                domain=excluded.domain,
                topic=excluded.topic,
                model_version=excluded.model_version,
                vector_json=excluded.vector_json,
                source_hash=excluded.source_hash
            """,
            [
                (
                    str(r.get("embedding_id", "")),
                    str(r.get("chunk_id", "")),
                    str(r.get("evidence_id", "")),
                    str(r.get("domain", "")),
                    str(r.get("topic", "general")),
                    str(r.get("model_version", "")),
                    json.dumps(r.get("vector", []), ensure_ascii=False),
                    str(r.get("source_hash", "")),
                )
                for r in embedding_records
            ],
        )
        conn.commit()
    finally:
        conn.close()


def build_embeddings(
    *,
    domain: str,
    input_path: Path,
    output_path: Path,
    dry_run: bool = False,
    output_format: str = "json",
    sqlite_path: Path | None = None,
) -> dict[str, Any]:
    index_file = input_path / "index.json" if input_path.is_dir() else input_path
    entries = _load_index(index_file)

    embedding_records: list[dict[str, Any]] = []
    for item in entries:
        source_text = str(item.get("content_preview", ""))
        chunk_id = str(item.get("chunk_id", ""))
        evidence_id = str(item.get("evidence_id", ""))
        record = {
            "embedding_id": f"emb_{chunk_id or evidence_id}",
            "chunk_id": chunk_id,
            "evidence_id": evidence_id,
            "domain": item.get("domain", domain),
            "topic": item.get("topic", "general"),
            "model_version": MODEL_VERSION,
            "vector": _hash_vector(source_text),
            "source_hash": item.get("hash_sha256", ""),
        }
        embedding_records.append(record)

    embedding_records.sort(key=lambda r: (str(r["domain"]), str(r["topic"]), str(r["chunk_id"])))

    report = {
        "stage": "embedding_builder",
        "domain": domain,
        "input": input_path.as_posix(),
        "output": output_path.as_posix(),
        "output_format": output_format,
        "created": len(embedding_records),
        "updated": 0,
        "skipped": 0,
        "warnings": [],
        "errors": [],
    }

    if dry_run:
        return report

    output_path.mkdir(parents=True, exist_ok=True)

    if output_format in {"json", "both"}:
        (output_path / "embeddings.json").write_text(
            json.dumps(embedding_records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    if output_format in {"sqlite", "both"}:
        db_path = sqlite_path if sqlite_path is not None else (output_path / "embeddings.db")
        _write_sqlite(db_path, embedding_records)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic embedding builder: 40_index_* -> 50_embedding_*")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--input", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--report", default="")
    parser.add_argument("--config", default="")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--output-format", choices=["json", "sqlite", "both"], default="json")
    parser.add_argument("--sqlite-path", default="")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else (Path.cwd() / f"40_index_{args.domain}")
    output_path = Path(args.output) if args.output else (Path.cwd() / f"50_embedding_{args.domain}")
    report_path = Path(args.report) if args.report else (output_path / "embedding_report.json")

    if not input_path.exists():
        print(f"input missing: {input_path}")
        return 1

    run_report = build_embeddings(
        domain=args.domain,
        input_path=input_path,
        output_path=output_path,
        dry_run=args.dry_run,
        output_format=args.output_format,
        sqlite_path=Path(args.sqlite_path) if args.sqlite_path else None,
    )

    if not args.dry_run:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(run_report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        "created={c} updated={u} skipped={s} errors={e}".format(
            c=run_report["created"],
            u=run_report["updated"],
            s=run_report["skipped"],
            e=len(run_report["errors"]),
        )
    )
    return 0 if not run_report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())