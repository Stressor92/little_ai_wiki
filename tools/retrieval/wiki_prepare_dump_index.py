from __future__ import annotations

import argparse
import bz2
from collections.abc import Iterable
from datetime import datetime, timezone
import json
import lzma
from pathlib import Path
import re
import sqlite3
import xml.etree.ElementTree as ET


NAMESPACE_PREFIXES = (
    "file:",
    "category:",
    "talk:",
    "template:",
    "wikipedia:",
    "help:",
    "portal:",
    "draft:",
    "module:",
    "special:",
    "mediawiki:",
)


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in value)
    return "_".join(cleaned.split()) or "na"


def _open_xml(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".bz2":
        return bz2.open(path, "rb")
    if suffix == ".xz":
        return lzma.open(path, "rb")
    return path.open("rb")


def _strip_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _normalize_title(raw: str) -> str:
    value = (raw or "").strip().replace("_", " ")
    if not value:
        return ""
    return value[0].upper() + value[1:]


def _extract_target_from_redirect(value: str) -> str:
    m = re.search(r"#REDIRECT\s*\[\[(.*?)\]\]", value, flags=re.IGNORECASE)
    if not m:
        return ""
    raw = m.group(1).split("#", 1)[0].split("|", 1)[0].strip()
    return _normalize_title(raw)


def _extract_links(wikitext: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]", wikitext):
        target = _normalize_title(match.group(1))
        if not target:
            continue
        lowered = target.lower()
        if any(lowered.startswith(prefix) for prefix in NAMESPACE_PREFIXES):
            continue
        if target in seen:
            continue
        seen.add(target)
        links.append(target)
    return links


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pages (
            title TEXT PRIMARY KEY,
            page_id INTEGER,
            revision_id INTEGER,
            updated_at TEXT,
            wikitext TEXT NOT NULL,
            links_json TEXT NOT NULL,
            redirect_target TEXT,
            is_redirect INTEGER NOT NULL DEFAULT 0,
            source_path TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_page_id ON pages(page_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_redirect ON pages(redirect_target)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def _upsert_page(
    conn: sqlite3.Connection,
    *,
    title: str,
    page_id: int,
    revision_id: int,
    updated_at: str,
    wikitext: str,
    links: list[str],
    redirect_target: str,
    source_path: str,
) -> None:
    conn.execute(
        """
        INSERT INTO pages (
            title, page_id, revision_id, updated_at, wikitext, links_json,
            redirect_target, is_redirect, source_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(title) DO UPDATE SET
            page_id=excluded.page_id,
            revision_id=excluded.revision_id,
            updated_at=excluded.updated_at,
            wikitext=excluded.wikitext,
            links_json=excluded.links_json,
            redirect_target=excluded.redirect_target,
            is_redirect=excluded.is_redirect,
            source_path=excluded.source_path
        """,
        (
            title,
            page_id,
            revision_id,
            updated_at,
            wikitext,
            json.dumps(links, ensure_ascii=False),
            redirect_target,
            1 if redirect_target else 0,
            source_path,
        ),
    )


def _iter_pages(dump_path: Path) -> Iterable[dict]:
    with _open_xml(dump_path) as f:
        context = ET.iterparse(f, events=("start", "end"))
        _, root = next(context)

        current: dict | None = None
        in_revision = False

        for event, elem in context:
            tag = _strip_tag(elem.tag)
            if event == "start" and tag == "page":
                current = {
                    "title": "",
                    "ns": "",
                    "page_id": "",
                    "revision_id": "",
                    "timestamp": "",
                    "text": "",
                    "redirect": "",
                    "_page_id_seen": False,
                    "_revision_id_seen": False,
                }
                in_revision = False
                continue

            if current is None:
                continue

            if event == "start" and tag == "revision":
                in_revision = True
                continue

            if event == "end":
                text = elem.text or ""
                if tag == "title" and not current["title"]:
                    current["title"] = text
                elif tag == "ns" and not current["ns"]:
                    current["ns"] = text
                elif tag == "id":
                    if in_revision and not current["_revision_id_seen"]:
                        current["revision_id"] = text
                        current["_revision_id_seen"] = True
                    elif not in_revision and not current["_page_id_seen"]:
                        current["page_id"] = text
                        current["_page_id_seen"] = True
                elif tag == "timestamp" and in_revision and not current["timestamp"]:
                    current["timestamp"] = text
                elif tag == "text" and in_revision:
                    current["text"] = text
                elif tag == "redirect":
                    current["redirect"] = elem.attrib.get("title", "")
                elif tag == "revision":
                    in_revision = False
                elif tag == "page":
                    yield current
                    current = None
                    root.clear()

                elem.clear()


def build_index(
    *,
    dump_path: Path,
    db_path: Path,
    dry_run: bool,
    force: bool,
    report_path: Path | None,
) -> dict:
    if not dump_path.exists():
        raise FileNotFoundError(f"Dump path not found: {dump_path}")

    if db_path.exists() and force and not dry_run:
        db_path.unlink()

    report = {
        "tool": "wiki_prepare_dump_index",
        "input": str(dump_path),
        "output": str(db_path),
        "discovered": 0,
        "changed": [],
        "skipped": [],
        "warnings": {},
        "errors": {},
        "stats": {
            "pages_total": 0,
            "pages_ns0": 0,
            "redirects": 0,
            "bytes_in": dump_path.stat().st_size,
            "bytes_out": 0,
        },
    }

    if dry_run:
        for page in _iter_pages(dump_path):
            report["stats"]["pages_total"] += 1
            if page.get("ns") == "0":
                report["stats"]["pages_ns0"] += 1
                report["discovered"] += 1
        if report_path is not None:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        changed = 0
        for page in _iter_pages(dump_path):
            report["stats"]["pages_total"] += 1
            if page.get("ns") != "0":
                continue

            title = _normalize_title(page.get("title", ""))
            if not title:
                report["skipped"].append("empty_title")
                continue

            text = page.get("text", "") or ""
            if not text.strip():
                continue

            report["stats"]["pages_ns0"] += 1
            report["discovered"] += 1

            redirect_target = ""
            redirect_attr = _normalize_title(page.get("redirect", ""))
            if redirect_attr:
                redirect_target = redirect_attr
            else:
                redirect_target = _extract_target_from_redirect(text)

            if redirect_target:
                report["stats"]["redirects"] += 1

            links = _extract_links(text)
            try:
                page_id = int(page.get("page_id", "0") or "0")
                revision_id = int(page.get("revision_id", "0") or "0")
            except ValueError:
                page_id = 0
                revision_id = 0

            _upsert_page(
                conn,
                title=title,
                page_id=page_id,
                revision_id=revision_id,
                updated_at=page.get("timestamp", ""),
                wikitext=text,
                links=links,
                redirect_target=redirect_target,
                source_path=str(dump_path),
            )
            changed += 1

        now = datetime.now(timezone.utc).isoformat()
        conn.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES('created_at', ?)", (now,))
        conn.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES('dump_path', ?)", (str(dump_path),))
        conn.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', '1')")
        conn.commit()

    report["changed"].append(str(db_path))
    report["stats"]["bytes_out"] = db_path.stat().st_size if db_path.exists() else 0

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build local SQLite index from offline English Wikipedia XML dump."
    )
    parser.add_argument("--domain", required=True)
    parser.add_argument("--input", required=True, help="Path to enwiki XML dump (.xml/.bz2/.xz)")
    parser.add_argument("--output", default="", help="Path to output sqlite DB")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Overwrite existing index DB")
    parser.add_argument("--report", default="", help="Optional JSON report path")
    parser.add_argument("--config", default="")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dump_path = Path(args.input)
    db_path = Path(args.output) if args.output else Path.cwd() / f"00_raw_{args.domain}" / "wikipedia" / "wikipedia_index.sqlite"
    report_path = Path(args.report) if args.report else None

    try:
        report = build_index(
            dump_path=dump_path,
            db_path=db_path,
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