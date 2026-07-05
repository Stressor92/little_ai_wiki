#!/usr/bin/env python3
"""
tools/retrieval/download.py
Standalone downloader: loads papers from DB into 00_raw_medical/.

Usage:
    python tools/retrieval/download.py
    python tools/retrieval/download.py --topic schlaf
    python tools/retrieval/download.py --max 50
    python tools/retrieval/download.py --min-score 0.6
"""

import sys
import asyncio
import argparse
import logging
import json
from pathlib import Path

# Make repo root importable when running this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.shared.config import DB_PATH, RAW_DIR, RAW_SOURCES
from tools.shared.database import get_all_papers, get_papers_for_topic
from tools.retrieval.downloader import download_batch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def parse_args():
    p = argparse.ArgumentParser(description="Paper-Downloader")
    p.add_argument("--domain", required=True)
    p.add_argument("--input", default=str(DB_PATH), help="Path to SQLite DB")
    p.add_argument("--output", default=str(RAW_DIR), help="Output raw folder")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--report", default="", help="Optional JSON run report")
    p.add_argument("--config", default="")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--topic",     default=None, help="Nur bestimmtes Topic")
    p.add_argument("--max",       type=int, default=100, help="Max Downloads")
    p.add_argument("--min-score", type=float, default=0.4)
    p.add_argument("--list",      action="store_true", help="Nur auflisten, nicht herunterladen")
    return p.parse_args()


async def main():
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    db_path = Path(args.input)
    raw_dir = Path(args.output)

    # Verzeichnisse sicherstellen
    for s in RAW_SOURCES:
        (raw_dir / s).mkdir(parents=True, exist_ok=True)

    if args.topic:
        papers = get_papers_for_topic(db_path, args.topic, min_score=args.min_score)
        print(f"Topic '{args.topic}': {len(papers)} Paper")
    else:
        papers = get_all_papers(db_path, min_score=args.min_score)
        print(f"Gesamt: {len(papers)} Paper")

    oa_pending = [p for p in papers if p.get("is_open_access") and not p.get("downloaded")]
    print(f"Open Access, noch nicht geladen: {len(oa_pending)}")

    if args.list or args.dry_run:
        for p in oa_pending[:50]:
            print(f"  [{p.get('relevance_score',0):.2f}] {p.get('title','')[:70]}")
        downloaded = 0
    else:
        downloaded = await download_batch(oa_pending, db_path, max_downloads=args.max)
        print(f"\n✓ {downloaded} Paper heruntergeladen → {raw_dir}")

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tool": "download",
            "domain": args.domain,
            "db_path": str(db_path),
            "raw_dir": str(raw_dir),
            "topic": args.topic,
            "max": args.max,
            "min_score": args.min_score,
            "dry_run": args.dry_run,
            "selected": len(oa_pending),
            "downloaded": downloaded,
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
