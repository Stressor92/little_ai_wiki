#!/usr/bin/env python3
"""
tools/retrieval/inspect_db.py
Shows statistics and papers from the database.

Usage:
    python tools/retrieval/inspect_db.py             # overview
    python tools/retrieval/inspect_db.py --topic schlaf
    python tools/retrieval/inspect_db.py --top 20
    python tools/retrieval/inspect_db.py --export csv
"""

import sys
import json
import csv
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.shared.config import DB_PATH, TOPICS
from tools.shared.database import get_all_papers, get_papers_for_topic, get_stats


def parse_args():
    p = argparse.ArgumentParser(description="DB Inspector")
    p.add_argument("--domain", required=True)
    p.add_argument("--input", default=str(DB_PATH), help="Path to SQLite DB")
    p.add_argument("--output", default="", help="Output directory for exports")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--report", default="", help="Optional JSON run report")
    p.add_argument("--config", default="")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--topic",  default=None)
    p.add_argument("--top",    type=int, default=None)
    p.add_argument("--export", choices=["csv", "json"], default=None)
    p.add_argument("--min-score", type=float, default=0.0)
    return p.parse_args()


def main():
    args = parse_args()
    db_path = Path(args.input)
    export_root = Path(args.output).resolve() if args.output else Path.cwd()
    export_root.mkdir(parents=True, exist_ok=True)

    if args.topic and args.topic not in TOPICS:
        print(f"WARN: topic '{args.topic}' not in configured TOPICS; continuing.")

    stats = get_stats(db_path)
    print(f"\n{'═'*50}")
    print(f"  Datenbank: {db_path}")
    print(f"  Paper gesamt:   {stats['total']}")
    print(f"  Heruntergeladen:{stats['downloaded']}")
    print(f"  Open Access:    {stats['open_access']}")
    print(f"  Nach Quelle:    {stats['by_source']}")
    print(f"{'═'*50}\n")

    if args.topic:
        papers = get_papers_for_topic(db_path, args.topic, min_score=args.min_score)
        print(f"Topic '{args.topic}': {len(papers)} Paper\n")
    elif args.top:
        papers = get_all_papers(db_path, min_score=args.min_score)[:args.top]
        print(f"Top {args.top} Paper:\n")
    else:
        # Nur Stats
        print("Top 5 Paper:")
        for p in stats["top_papers"]:
            print(f"  [{p['score']:.2f}] {p['title'][:70]}")
        papers = []

    for i, p in enumerate(papers, 1):
        print(f"{i:3}. [{p.get('relevance_score',0):.2f}] {p.get('title','')[:70]}")
        print(f"      {p.get('source','')} | {p.get('study_type','?')} | {p.get('year','?')}")
        if p.get("key_finding"):
            print(f"      💡 {p['key_finding'][:100]}")
        print()

    if args.export and papers:
        out = export_root / f"export_{args.topic or 'all'}.{args.export}"
        if out.exists() and not args.force:
            print(f"ERROR: export file exists: {out} (use --force to overwrite)")
            return 1
        if args.export == "csv":
            if args.dry_run:
                print(f"DRY-RUN: would export CSV to {out}")
            else:
                with open(out, "w", newline="", encoding="utf-8") as f:
                    cols = ["id", "title", "source", "study_type", "year",
                            "relevance_score", "key_finding", "risk", "limitations",
                            "is_open_access", "url"]
                    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
                    w.writeheader()
                    w.writerows(papers)
        elif args.export == "json":
            for p in papers:
                for k in ("authors", "topics"):
                    if isinstance(p.get(k), str):
                        try:
                            p[k] = json.loads(p[k])
                        except Exception:
                            pass
            if args.dry_run:
                print(f"DRY-RUN: would export JSON to {out}")
            else:
                out.write_text(json.dumps(papers, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✓ Export-Ziel: {out}")

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tool": "inspect_db",
            "domain": args.domain,
            "db_path": str(db_path),
            "topic": args.topic,
            "top": args.top,
            "export": args.export,
            "dry_run": args.dry_run,
            "count": len(papers),
            "stats": stats,
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
