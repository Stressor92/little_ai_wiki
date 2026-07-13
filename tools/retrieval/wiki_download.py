from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


def _dump_scalar(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _build_frontmatter(meta: dict) -> str:
    keys = [
        "source",
        "source_url",
        "language",
        "license",
        "title",
        "page_id",
        "revision_id",
        "updated_at",
        "depth",
        "parent_title",
        "seed_titles",
        "dump_snapshot",
        "fetched_at",
        "lineage_source_id",
        "lineage_document_id",
    ]
    lines = ["---"]
    for key in keys:
        if key in meta:
            lines.append(f"{key}: {_dump_scalar(meta[key])}")
    lines.append("---")
    return "\n".join(lines)


def _compose_document(meta: dict, wikitext: str) -> str:
    return _build_frontmatter(meta) + "\n\n" + wikitext


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end = idx
            break
    if end is None:
        return {}, text

    meta: dict = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, raw_val = line.split(":", 1)
        key = key.strip()
        raw_val = raw_val.strip()
        if not key:
            continue
        try:
            meta[key] = json.loads(raw_val)
        except Exception:
            meta[key] = raw_val.strip('"')

    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    return meta, body


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in value)
    return "_".join(cleaned.split()) or "na"


def _normalize_title(raw: str) -> str:
    value = (raw or "").strip().replace("_", " ")
    if not value:
        return ""
    return value[0].upper() + value[1:]


def _split_seeds(raw: str) -> list[str]:
    values = [v.strip() for v in raw.split(",")]
    return [_normalize_title(v) for v in values if v.strip()]


def _resolve_page(conn: sqlite3.Connection, title: str, max_hops: int = 8) -> tuple[str, dict | None]:
    current = _normalize_title(title)
    seen: set[str] = set()
    for _ in range(max_hops):
        if not current or current in seen:
            return current, None
        seen.add(current)

        row = conn.execute(
            """
            SELECT title, page_id, revision_id, updated_at, wikitext, links_json,
                   redirect_target, is_redirect, source_path
            FROM pages
            WHERE title = ?
            """,
            (current,),
        ).fetchone()
        if row is None:
            return current, None

        page = {
            "title": row[0],
            "page_id": row[1],
            "revision_id": row[2],
            "updated_at": row[3],
            "wikitext": row[4],
            "links": json.loads(row[5] or "[]"),
            "redirect_target": row[6] or "",
            "is_redirect": bool(row[7]),
            "source_path": row[8],
        }

        target = _normalize_title(page["redirect_target"])
        if page["is_redirect"] and target and target != current:
            current = target
            continue
        return current, page

    return current, None


def run_download(
    *,
    domain: str,
    output_dir: Path,
    index_db_path: Path,
    seeds: list[str],
    depth: int,
    max_articles: int,
    dry_run: bool,
    force: bool,
    report_path: Path | None,
) -> dict:
    report = {
        "tool": "wiki_download",
        "domain": domain,
        "input": str(index_db_path),
        "output": str(output_dir),
        "depth": depth,
        "max_articles": max_articles,
        "seeds": seeds,
        "discovered": 0,
        "changed": [],
        "skipped": [],
        "warnings": {},
        "errors": {},
        "stats": {
            "written_articles": 0,
            "redirect_hits": 0,
            "missing_titles": 0,
            "bytes_out": 0,
        },
    }

    if not index_db_path.exists():
        raise FileNotFoundError(f"Index database not found: {index_db_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict] = []

    with sqlite3.connect(index_db_path) as conn:
        queue: deque[tuple[str, int, str]] = deque((seed, 0, "") for seed in seeds)
        visited: set[str] = set()

        while queue and len(visited) < max_articles:
            raw_title, cur_depth, parent = queue.popleft()
            title = _normalize_title(raw_title)
            if not title:
                continue

            canonical, page = _resolve_page(conn, title)
            if page is None:
                report["stats"]["missing_titles"] += 1
                report["warnings"].setdefault(title, []).append("not found in offline index")
                continue

            if canonical in visited:
                continue

            if canonical != title:
                report["stats"]["redirect_hits"] += 1

            visited.add(canonical)
            report["discovered"] += 1

            slug = _slug(canonical)
            text_path = output_dir / f"wikipedia_{slug}.txt"
            legacy_meta_path = output_dir / f"wikipedia_{slug}_metadata.json"

            meta = {
                "source": "wikipedia_offline_dump",
                "source_url": f"https://en.wikipedia.org/wiki/{canonical.replace(' ', '_')}",
                "language": "en",
                "license": "CC-BY-SA-4.0 and GFDL",
                "title": canonical,
                "page_id": page["page_id"],
                "revision_id": page["revision_id"],
                "updated_at": page["updated_at"],
                "depth": cur_depth,
                "parent_title": parent,
                "seed_titles": seeds,
                "dump_snapshot": page["source_path"],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "lineage_source_id": f"wiki_en_{slug}",
                "lineage_document_id": f"{domain}_wiki_{slug}",
            }
            doc_text = _compose_document(meta, page["wikitext"])

            should_write = force or not text_path.exists()
            if not should_write and text_path.exists():
                current_text = text_path.read_text(encoding="utf-8")
                current_meta, _ = _parse_frontmatter(current_text)
                if not current_meta:
                    should_write = True
            if dry_run:
                report["changed"].append(str(text_path))
                if legacy_meta_path.exists():
                    report["changed"].append(str(legacy_meta_path))
            elif should_write:
                text_path.write_text(doc_text, encoding="utf-8")
                report["changed"].append(str(text_path))
                report["stats"]["written_articles"] += 1
                report["stats"]["bytes_out"] += text_path.stat().st_size
                if legacy_meta_path.exists():
                    legacy_meta_path.unlink()
                    report["changed"].append(str(legacy_meta_path))
            else:
                report["skipped"].append(str(text_path))

            manifest_rows.append(
                {
                    "title": canonical,
                    "depth": cur_depth,
                    "text_path": str(text_path),
                    "embedded_metadata": True,
                }
            )

            if cur_depth >= depth:
                continue

            for linked in page["links"]:
                if len(visited) + len(queue) >= max_articles * 3:
                    break
                queue.append((linked, cur_depth + 1, canonical))

    manifest_path = output_dir / "wikipedia_manifest.json"
    if not dry_run:
        manifest_payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "domain": domain,
            "depth": depth,
            "max_articles": max_articles,
            "seed_titles": seeds,
            "articles": manifest_rows,
        }
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        report["changed"].append(str(manifest_path))

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download English Wikipedia articles from local offline index by seeds and link depth."
    )
    parser.add_argument("--domain", required=True)
    parser.add_argument("--input", default="", help="Path to local wikipedia index sqlite DB")
    parser.add_argument("--output", default="", help="Output folder, e.g. 00_raw_health/wikipedia")
    parser.add_argument("--seeds", required=True, help="Comma-separated seed article titles")
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--max-articles", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--report", default="")
    parser.add_argument("--config", default="")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.depth < 0:
        print("depth must be >= 0")
        return 1
    if args.max_articles <= 0:
        print("max-articles must be > 0")
        return 1

    seeds = _split_seeds(args.seeds)
    if not seeds:
        print("seeds must not be empty")
        return 1

    index_path = (
        Path(args.input)
        if args.input
        else Path.cwd() / f"00_raw_{args.domain}" / "wikipedia" / "wikipedia_index.sqlite"
    )
    output_dir = (
        Path(args.output)
        if args.output
        else Path.cwd() / f"00_raw_{args.domain}" / "wikipedia"
    )
    report_path = Path(args.report) if args.report else None

    try:
        report = run_download(
            domain=args.domain,
            output_dir=output_dir,
            index_db_path=index_path,
            seeds=seeds,
            depth=args.depth,
            max_articles=args.max_articles,
            dry_run=args.dry_run,
            force=args.force,
            report_path=report_path,
        )
    except FileNotFoundError as exc:
        print(str(exc))
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Execution failed: {exc}")
        return 2

    print(
        "discovered={d} changed={c} skipped={s} warnings={w} errors={e}".format(
            d=report["discovered"],
            c=len(report["changed"]),
            s=len(report["skipped"]),
            w=len(report["warnings"]),
            e=len(report["errors"]),
        )
    )
    return 0 if not report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())