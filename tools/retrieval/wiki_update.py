from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys


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
        "updated_from_dump_at",
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


def _discover_existing_articles(output_dir: Path) -> list[dict]:
    found: list[dict] = []
    for text_path in sorted(output_dir.glob("wikipedia_*.txt"), key=lambda p: p.name.lower()):
        text = text_path.read_text(encoding="utf-8")
        fm_meta, _ = _parse_frontmatter(text)

        legacy_meta_path = output_dir / f"{text_path.stem}_metadata.json"
        legacy_meta: dict = {}
        if legacy_meta_path.exists():
            try:
                legacy_meta = json.loads(legacy_meta_path.read_text(encoding="utf-8"))
            except Exception:
                legacy_meta = {}

        title = _normalize_title(str(fm_meta.get("title", "")))
        if not title:
            title = _normalize_title(str(legacy_meta.get("title", "")))
        if not title:
            guess = text_path.stem.replace("wikipedia_", "", 1).replace("_", " ")
            title = _normalize_title(guess)

        if title:
            found.append(
                {
                    "text_path": text_path,
                    "title": title,
                    "frontmatter": fm_meta,
                    "legacy_meta_path": legacy_meta_path if legacy_meta_path.exists() else None,
                    "legacy_meta": legacy_meta,
                }
            )

    return found


def _run_module(module: str, args: list[str]) -> tuple[int, str, str]:
    cmd = [sys.executable, "-m", module, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def run_update(
    *,
    domain: str,
    output_dir: Path,
    index_db_path: Path,
    dry_run: bool,
    force: bool,
    run_pipeline: str,
    pipeline_input: Path,
    pipeline_output: Path,
    pipeline_force: bool,
    report_path: Path | None,
) -> tuple[dict, int]:
    if not index_db_path.exists():
        raise FileNotFoundError(f"Index database not found: {index_db_path}")
    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory not found: {output_dir}")

    report = {
        "tool": "wiki_update",
        "domain": domain,
        "input": str(index_db_path),
        "output": str(output_dir),
        "pipeline": run_pipeline,
        "discovered": 0,
        "changed": [],
        "skipped": [],
        "warnings": {},
        "errors": {},
        "stats": {
            "existing_articles": 0,
            "updated_articles": 0,
            "unchanged_articles": 0,
            "missing_in_index": 0,
            "bytes_out": 0,
        },
    }

    existing = _discover_existing_articles(output_dir)
    report["stats"]["existing_articles"] = len(existing)

    with sqlite3.connect(index_db_path) as conn:
        for item in existing:
            text_path = item["text_path"]
            title = item["title"]
            legacy_meta_path = item["legacy_meta_path"]
            old_meta = item["frontmatter"]

            report["discovered"] += 1
            canonical, page = _resolve_page(conn, title)
            if page is None:
                report["stats"]["missing_in_index"] += 1
                report["warnings"].setdefault(title, []).append("not found in offline index")
                continue

            if not old_meta and item["legacy_meta"]:
                old_meta = item["legacy_meta"]
            text_raw = text_path.read_text(encoding="utf-8")
            _, old_wikitext = _parse_frontmatter(text_raw)

            is_changed = (
                force
                or old_wikitext != page["wikitext"]
                or str(old_meta.get("revision_id", "")) != str(page["revision_id"])
                or str(old_meta.get("updated_at", "")) != str(page["updated_at"])
                or _normalize_title(str(old_meta.get("title", ""))) != canonical
            )

            if not is_changed:
                report["stats"]["unchanged_articles"] += 1
                report["skipped"].append(str(text_path))
                continue

            slug = _slug(canonical)
            next_text_path = output_dir / f"wikipedia_{slug}.txt"

            new_meta = dict(old_meta)
            new_meta.update(
                {
                    "source": "wikipedia_offline_dump",
                    "source_url": f"https://en.wikipedia.org/wiki/{canonical.replace(' ', '_')}",
                    "language": "en",
                    "license": "CC-BY-SA-4.0 and GFDL",
                    "title": canonical,
                    "page_id": page["page_id"],
                    "revision_id": page["revision_id"],
                    "updated_at": page["updated_at"],
                    "dump_snapshot": page["source_path"],
                    "updated_from_dump_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            new_meta.setdefault("lineage_source_id", f"wiki_en_{slug}")
            new_meta.setdefault("lineage_document_id", f"{domain}_wiki_{slug}")

            new_doc = _compose_document(new_meta, page["wikitext"])

            if dry_run:
                report["changed"].append(str(next_text_path))
                if next_text_path != text_path:
                    report["skipped"].append(str(text_path))
                if legacy_meta_path is not None:
                    report["changed"].append(str(legacy_meta_path))
                report["stats"]["updated_articles"] += 1
                continue

            next_text_path.write_text(new_doc, encoding="utf-8")
            report["changed"].append(str(next_text_path))
            report["stats"]["updated_articles"] += 1
            report["stats"]["bytes_out"] += next_text_path.stat().st_size

            # Keep layer-00 folder clean when titles changed by redirect/canonicalization.
            if next_text_path != text_path and text_path.exists():
                text_path.unlink()
                report["changed"].append(str(text_path))
            if legacy_meta_path is not None and legacy_meta_path.exists():
                legacy_meta_path.unlink()
                report["changed"].append(str(legacy_meta_path))

    pipeline_exit_code = 0
    if run_pipeline != "none" and report["stats"]["updated_articles"] > 0 and not dry_run:
        module = "tools.pipelines.pipeline_incremental" if run_pipeline == "incremental" else "tools.pipelines.pipeline_full"
        cmd_args = [
            "--domain",
            domain,
            "--input",
            str(pipeline_input),
            "--output",
            str(pipeline_output),
        ]
        if pipeline_force:
            cmd_args.append("--force")

        code, stdout, stderr = _run_module(module, cmd_args)
        pipeline_exit_code = code
        pipeline_result = {
            "module": module,
            "exit_code": code,
            "stdout": stdout.strip(),
            "stderr": stderr.strip(),
        }
        report["pipeline_result"] = pipeline_result
        if code != 0:
            report["errors"]["pipeline"] = stderr.strip() or stdout.strip() or f"{module} failed"

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return report, pipeline_exit_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update existing offline Wikipedia raw pages to latest local dump state and optionally rerun pipeline."
    )
    parser.add_argument("--domain", required=True)
    parser.add_argument("--input", default="", help="Path to local wikipedia index sqlite DB")
    parser.add_argument("--output", default="", help="Path to 00_raw_<domain>/wikipedia folder")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Rewrite all discovered pages")
    parser.add_argument("--report", default="")
    parser.add_argument("--config", default="")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--run-pipeline",
        choices=("none", "incremental", "full"),
        default="incremental",
        help="Pipeline mode after successful raw updates.",
    )
    parser.add_argument(
        "--pipeline-input",
        default="",
        help="Pipeline input root (defaults to 00_raw_<domain>).",
    )
    parser.add_argument(
        "--pipeline-output",
        default="",
        help="Pipeline output root (defaults to workspace root).",
    )
    parser.add_argument(
        "--pipeline-force",
        action="store_true",
        help="Forward --force to the pipeline runner.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

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
    report_path = (
        Path(args.report)
        if args.report
        else output_dir / "wiki_update_report.json"
    )
    pipeline_input = (
        Path(args.pipeline_input)
        if args.pipeline_input
        else Path.cwd() / f"00_raw_{args.domain}"
    )
    pipeline_output = Path(args.pipeline_output) if args.pipeline_output else Path.cwd()

    try:
        report, pipeline_exit = run_update(
            domain=args.domain,
            output_dir=output_dir,
            index_db_path=index_path,
            dry_run=args.dry_run,
            force=args.force,
            run_pipeline=args.run_pipeline,
            pipeline_input=pipeline_input,
            pipeline_output=pipeline_output,
            pipeline_force=args.pipeline_force,
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

    if report["errors"]:
        return 2
    if pipeline_exit != 0:
        return pipeline_exit
    return 0


if __name__ == "__main__":
    raise SystemExit(main())