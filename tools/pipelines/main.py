#!/usr/bin/env python3
"""
Health Wiki Builder
Scrapt wissenschaftliche Paper und baut ein personalisiertes Wiki.
"""

import asyncio
import argparse
import logging
import json
from pathlib import Path

from tools.shared.config import TOPICS, USER_PROFILE, OUTPUT_DIR
from tools.pipelines.pipeline import WikiPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def parse_args():
    p = argparse.ArgumentParser(description="Health Wiki Builder")
    p.add_argument("--domain", required=True)
    p.add_argument("--input", default="")
    p.add_argument("--output", default="")
    p.add_argument("--force", action="store_true")
    p.add_argument("--report", default="")
    p.add_argument("--config", default="")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--topics",        nargs="+", default=None,
                   help=f"Topics: {list(TOPICS.keys())}")
    p.add_argument("--max-per-topic", type=int,   default=20)
    p.add_argument("--min-score",     type=float, default=0.4)
    p.add_argument("--rebuild-wiki",  action="store_true",
                   help="Wiki + Index neu aus DB generieren")
    p.add_argument("--dry-run",       action="store_true",
                   help="Nur Vorschau, nichts speichern")
    return p.parse_args()


async def main():
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    topics = TOPICS
    if args.topics:
        topics = {k: v for k, v in TOPICS.items() if k in args.topics}
        if not topics:
            log.error(f"Unbekannte Topics. Verfügbar: {list(TOPICS.keys())}")
            return

    log.info("═" * 60)
    log.info("  Health Wiki Builder")
    log.info(f"  Profil: {USER_PROFILE['age']}J · {USER_PROFILE['gender']} · {USER_PROFILE['occupation']}")
    log.info(f"  Topics: {len(topics)}  |  Max/Topic: {args.max_per_topic}  |  Min-Score: {args.min_score}")
    log.info("═" * 60)

    pipeline = WikiPipeline(
        topics=topics,
        user_profile=USER_PROFILE,
        output_dir=Path(args.output).resolve() if args.output else OUTPUT_DIR,
        max_per_topic=args.max_per_topic,
        min_relevance_score=args.min_score,
        dry_run=args.dry_run,
    )

    if args.rebuild_wiki:
        log.info("Rebuild: Index + Wiki aus vorhandener DB...")
        from tools.shared.config import INDEX_JSON, DB_PATH
        from tools.indexing.indexer import build_index
        build_index(DB_PATH, INDEX_JSON, min_score=args.min_score)
        pipeline.build_wiki_only()
    else:
        await pipeline.run()

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tool": "pipelines_main",
            "domain": args.domain,
            "topics": sorted(list(topics.keys())),
            "max_per_topic": args.max_per_topic,
            "min_score": args.min_score,
            "dry_run": args.dry_run,
            "rebuild_wiki": args.rebuild_wiki,
            "output": str(Path(args.output).resolve() if args.output else OUTPUT_DIR),
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("✓ Fertig")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
