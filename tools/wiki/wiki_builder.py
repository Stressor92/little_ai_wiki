from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


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


def _write_file(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_wiki(*, domain: str, input_path: Path, output_path: Path, dry_run: bool = False) -> dict[str, Any]:
    index_file = input_path / "index.json" if input_path.is_dir() else input_path
    records = _load_index(index_file)

    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        by_topic[str(rec.get("topic", "general"))].append(rec)

    report = {
        "stage": "wiki_builder",
        "domain": domain,
        "input": input_path.as_posix(),
        "output": output_path.as_posix(),
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "warnings": [],
        "errors": [],
    }

    if dry_run:
        report["created"] = len(by_topic) + 1
        return report

    output_path.mkdir(parents=True, exist_ok=True)

    readme = [
        f"# Wiki {domain}",
        "",
        "## Topics",
        "",
    ]
    for topic in sorted(by_topic.keys()):
        topic_file = f"{topic}.md"
        readme.append(f"- [{topic}]({topic_file})")
    _write_file(output_path / "README.md", readme)
    report["created"] += 1

    for topic, items in sorted(by_topic.items(), key=lambda t: t[0]):
        items_sorted = sorted(items, key=lambda i: str(i.get("evidence_id", "")))
        lines = [
            f"# Topic {topic}",
            "",
            f"Domain: {domain}",
            f"Entries: {len(items_sorted)}",
            "",
        ]
        for item in items_sorted:
            lines.extend(
                [
                    f"## {item.get('evidence_id', 'evidence_unknown')}",
                    "",
                    f"- chunk_id: {item.get('chunk_id', '')}",
                    f"- document_id: {item.get('document_id', '')}",
                    f"- chapter_id: {item.get('chapter_id', '')}",
                    f"- token_count: {item.get('token_count', 0)}",
                    "",
                    (item.get("content_preview", "") or "").strip(),
                    "",
                ]
            )
        _write_file(output_path / f"{topic}.md", lines)
        report["created"] += 1

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic wiki builder: 40_index_* -> 60_wiki_*")
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

    input_path = Path(args.input) if args.input else (Path.cwd() / f"40_index_{args.domain}")
    output_path = Path(args.output) if args.output else (Path.cwd() / f"60_wiki_{args.domain}")
    report_path = Path(args.report) if args.report else (output_path / "wiki_report.json")

    if not input_path.exists():
        print(f"input missing: {input_path}")
        return 1

    run_report = build_wiki(domain=args.domain, input_path=input_path, output_path=output_path, dry_run=args.dry_run)

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
