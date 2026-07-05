from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tools.structure.utils import parse_frontmatter


def _count_tokens(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _discover_chunks(input_path: Path) -> list[Path]:
    files = [p for p in input_path.rglob("*.md") if p.is_file() and p.name != "INDEX.md"]
    return sorted(files, key=lambda p: p.as_posix().lower())


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_chunk(path: Path) -> tuple[dict[str, str], str]:
    raw = path.read_text(encoding="utf-8")
    parsed = parse_frontmatter(raw)
    return parsed.metadata, parsed.body


def build_index(*, domain: str, input_path: Path, output_path: Path, dry_run: bool = False) -> dict[str, Any]:
    chunks = _discover_chunks(input_path)
    records: list[dict[str, Any]] = []

    for chunk_file in chunks:
        meta, body = _load_chunk(chunk_file)
        chunk_id = meta.get("chunk_id") or chunk_file.stem
        evidence_id = f"evidence_{chunk_id}"
        topic = meta.get("topic", "general")
        token_count = int(meta.get("token_count", str(_count_tokens(body))) or 0)

        record = {
            "evidence_id": evidence_id,
            "chunk_id": chunk_id,
            "document_id": meta.get("document_id", ""),
            "chapter_id": meta.get("chapter_id", ""),
            "source_id": meta.get("source_id", ""),
            "domain": meta.get("domain", domain),
            "topic": topic,
            "token_count": token_count,
            "source_file": meta.get("source_file", chunk_file.name),
            "lineage": meta.get("lineage", {}),
            "score": round(min(1.0, token_count / 500.0), 4),
            "limitations": [],
            "content_preview": body[:400],
            "hash_sha256": _sha256_text(body),
        }
        records.append(record)

    records.sort(key=lambda r: (str(r["document_id"]), str(r["chapter_id"]), str(r["chunk_id"])))
    by_topic: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        by_topic.setdefault(str(rec["topic"]), []).append(rec)

    report = {
        "stage": "evidence_index",
        "domain": domain,
        "input": input_path.as_posix(),
        "output": output_path.as_posix(),
        "created": len(records),
        "updated": 0,
        "skipped": 0,
        "warnings": [],
        "errors": [],
    }

    if dry_run:
        return report

    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "index.json").write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    topic_dir = output_path / "by_topic"
    topic_dir.mkdir(parents=True, exist_ok=True)
    for topic, items in sorted(by_topic.items(), key=lambda t: t[0]):
        (topic_dir / f"{topic}.json").write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic evidence index builder: 30_chunk_* -> 40_index_*")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--input", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--report", default="")
    parser.add_argument("--config", default="")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else (Path.cwd() / f"30_chunk_{args.domain}")
    output_path = Path(args.output) if args.output else (Path.cwd() / f"40_index_{args.domain}")
    report_path = Path(args.report) if args.report else (output_path / "index_report.json")

    if not input_path.exists():
        print(f"input missing: {input_path}")
        return 1

    run_report = build_index(domain=args.domain, input_path=input_path, output_path=output_path, dry_run=args.dry_run)

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