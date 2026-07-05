from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.structure.utils import parse_frontmatter


LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
AUTOLINK_RE = re.compile(r"<((?:https?://)[^>]+)>")


@dataclass(frozen=True)
class LinkFinding:
    source_file: str
    target: str
    status: str
    detail: str


def _load_index_records(index_path: Path) -> list[dict[str, Any]]:
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
    except Exception:
        return []
    return []


def _md_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files = [p for p in root.rglob("*.md") if p.is_file()]
    return sorted(files, key=lambda p: p.as_posix().lower())


def _extract_links(text: str) -> list[str]:
    links = [m.group(1).strip() for m in LINK_RE.finditer(text)]
    links.extend(m.group(1).strip() for m in AUTOLINK_RE.finditer(text))
    out = []
    seen: set[str] = set()
    for link in links:
        if link and link not in seen:
            seen.add(link)
            out.append(link)
    return out


def _is_external_link(link: str) -> bool:
    parsed = urllib.parse.urlparse(link)
    return parsed.scheme in {"http", "https"}


def _is_ignored_link(link: str) -> bool:
    parsed = urllib.parse.urlparse(link)
    if link.startswith("#"):
        return True
    return parsed.scheme in {"mailto", "tel", "data"}


def _resolve_internal_target(link: str, base_file: Path) -> Path | None:
    parsed = urllib.parse.urlparse(link)
    target = parsed.path
    if not target:
        return None

    decoded = urllib.parse.unquote(target)
    raw = Path(decoded)
    if raw.is_absolute():
        return raw

    resolved = (base_file.parent / raw).resolve()
    if resolved.exists():
        return resolved

    if resolved.suffix == "":
        with_md = resolved.with_suffix(".md")
        if with_md.exists():
            return with_md

    return resolved


def _check_external_link(url: str, timeout_seconds: float, stale_days: int) -> tuple[str, str]:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "health-wiki-audit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310
            status = getattr(resp, "status", 200)
            last_modified = resp.headers.get("Last-Modified", "")
            if last_modified:
                try:
                    dt = datetime.strptime(last_modified, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
                    age_days = (datetime.now(timezone.utc) - dt).days
                    if age_days > stale_days:
                        return "stale", f"HTTP {status}, last-modified age={age_days}d"
                except Exception:
                    pass
            return "ok", f"HTTP {status}"
    except urllib.error.HTTPError as exc:
        return "error", f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        # Fallback to GET because some servers reject HEAD.
        req_get = urllib.request.Request(url, method="GET", headers={"User-Agent": "health-wiki-audit/1.0"})
        try:
            with urllib.request.urlopen(req_get, timeout=timeout_seconds) as resp:  # noqa: S310
                status = getattr(resp, "status", 200)
                return "ok", f"HTTP {status} (GET fallback)"
        except Exception as exc_get:  # noqa: BLE001
            return "error", f"{type(exc).__name__}: {exc}; GET fallback failed: {type(exc_get).__name__}: {exc_get}"


def _layer_ids_from_md(root: Path, fields: tuple[str, ...]) -> set[str]:
    ids: set[str] = set()
    for file in _md_files(root):
        if file.name == "INDEX.md" or file.name.lower().endswith("_toc.md"):
            continue
        try:
            fm = parse_frontmatter(file.read_text(encoding="utf-8"))
            for field in fields:
                value = str(fm.metadata.get(field, "")).strip()
                if value:
                    ids.add(value)
        except Exception:
            continue
    return ids


def audit_wiki(
    *,
    domain: str,
    index_input: Path,
    wiki_root: Path,
    layer10_root: Path,
    layer20_root: Path,
    layer30_root: Path,
    check_external_links: bool,
    timeout_seconds: float,
    stale_days: int,
) -> dict[str, Any]:
    index_file = index_input / "index.json" if index_input.is_dir() else index_input
    index_records = _load_index_records(index_file)

    wiki_files = _md_files(wiki_root)
    wiki_text_by_file: dict[str, str] = {}
    combined_wiki_text_parts: list[str] = []

    for file in wiki_files:
        text = file.read_text(encoding="utf-8")
        wiki_text_by_file[file.as_posix()] = text
        combined_wiki_text_parts.append(text)

    combined_wiki_text = "\n".join(combined_wiki_text_parts)

    layer10_document_ids = _layer_ids_from_md(layer10_root, ("document_id",))
    layer10_source_ids = _layer_ids_from_md(layer10_root, ("source_id",))
    layer20_chapter_ids = _layer_ids_from_md(layer20_root, ("chapter_id", "chapter"))
    layer30_chunk_ids = _layer_ids_from_md(layer30_root, ("chunk_id",))

    lineage_missing: list[dict[str, str]] = []
    source_summary: dict[str, dict[str, Any]] = {}
    record_results: list[dict[str, Any]] = []

    def appears(value: str) -> bool:
        return bool(value) and (value in combined_wiki_text)

    for rec in index_records:
        evidence_id = str(rec.get("evidence_id", "")).strip()
        chunk_id = str(rec.get("chunk_id", "")).strip()
        chapter_id = str(rec.get("chapter_id", "")).strip()
        document_id = str(rec.get("document_id", "")).strip()
        source_id = str(rec.get("source_id", "")).strip()
        source_key = source_id or document_id or evidence_id or chunk_id or "unknown_source"

        if chunk_id and chunk_id not in layer30_chunk_ids:
            lineage_missing.append({"layer": "30", "id": chunk_id, "evidence_id": evidence_id, "reason": "chunk_id not found in 30_chunk"})
        if chapter_id and chapter_id not in layer20_chapter_ids:
            lineage_missing.append({"layer": "20", "id": chapter_id, "evidence_id": evidence_id, "reason": "chapter_id not found in 20_chapter"})
        if document_id and document_id not in layer10_document_ids:
            lineage_missing.append({"layer": "10", "id": document_id, "evidence_id": evidence_id, "reason": "document_id not found in 10_md"})
        if source_id and source_id not in layer10_source_ids:
            lineage_missing.append({"layer": "10", "id": source_id, "evidence_id": evidence_id, "reason": "source_id not found in 10_md"})

        in_wiki_evidence = appears(evidence_id)
        in_wiki_chunk = appears(chunk_id)
        in_wiki_chapter = appears(chapter_id)
        in_wiki_document = appears(document_id)
        in_wiki_source = appears(source_id)

        references_layer30 = in_wiki_chunk
        references_layer20 = in_wiki_chapter
        references_layer10 = in_wiki_document or in_wiki_source
        integrated_in_wiki = in_wiki_evidence or references_layer30 or references_layer20 or references_layer10

        record_results.append(
            {
                "evidence_id": evidence_id,
                "chunk_id": chunk_id,
                "chapter_id": chapter_id,
                "document_id": document_id,
                "source_id": source_id,
                "in_wiki": {
                    "evidence_id": in_wiki_evidence,
                    "chunk_id": in_wiki_chunk,
                    "chapter_id": in_wiki_chapter,
                    "document_id": in_wiki_document,
                    "source_id": in_wiki_source,
                },
                "references": {
                    "layer30": references_layer30,
                    "layer20": references_layer20,
                    "layer10": references_layer10,
                },
                "integrated_in_wiki": integrated_in_wiki,
            }
        )

        s = source_summary.setdefault(
            source_key,
            {
                "source_key": source_key,
                "record_count": 0,
                "integrated": False,
                "has_layer30_ref": False,
                "has_layer20_ref": False,
                "has_layer10_ref": False,
            },
        )
        s["record_count"] += 1
        s["integrated"] = s["integrated"] or integrated_in_wiki
        s["has_layer30_ref"] = s["has_layer30_ref"] or references_layer30
        s["has_layer20_ref"] = s["has_layer20_ref"] or references_layer20
        s["has_layer10_ref"] = s["has_layer10_ref"] or references_layer10

    internal_links: list[LinkFinding] = []
    external_links: list[LinkFinding] = []

    for file in wiki_files:
        text = wiki_text_by_file[file.as_posix()]
        for link in _extract_links(text):
            if _is_ignored_link(link):
                continue

            if _is_external_link(link):
                if check_external_links:
                    status, detail = _check_external_link(link, timeout_seconds=timeout_seconds, stale_days=stale_days)
                    external_links.append(LinkFinding(source_file=file.as_posix(), target=link, status=status, detail=detail))
                else:
                    external_links.append(LinkFinding(source_file=file.as_posix(), target=link, status="skipped", detail="external link check disabled"))
                continue

            target = _resolve_internal_target(link, file)
            if target is None:
                internal_links.append(LinkFinding(source_file=file.as_posix(), target=link, status="error", detail="empty internal path"))
                continue
            if target.exists():
                internal_links.append(LinkFinding(source_file=file.as_posix(), target=link, status="ok", detail=target.as_posix()))
            else:
                internal_links.append(LinkFinding(source_file=file.as_posix(), target=link, status="error", detail=f"missing target: {target.as_posix()}"))

    source_rows = sorted(source_summary.values(), key=lambda x: str(x["source_key"]))

    missing_sources = [s for s in source_rows if not s["integrated"]]
    missing_layer30_refs = [s for s in source_rows if not s["has_layer30_ref"]]
    missing_layer20_refs = [s for s in source_rows if not s["has_layer20_ref"]]
    missing_layer10_refs = [s for s in source_rows if not s["has_layer10_ref"]]

    broken_internal_links = [l for l in internal_links if l.status == "error"]
    broken_external_links = [l for l in external_links if l.status == "error"]
    stale_external_links = [l for l in external_links if l.status == "stale"]

    return {
        "tool": "wiki_audit",
        "domain": domain,
        "index_file": index_file.as_posix(),
        "wiki_root": wiki_root.as_posix(),
        "layers": {
            "10_md": layer10_root.as_posix(),
            "20_chapter": layer20_root.as_posix(),
            "30_chunk": layer30_root.as_posix(),
        },
        "summary": {
            "index_records": len(index_records),
            "wiki_files": len(wiki_files),
            "sources_total": len(source_rows),
            "sources_integrated": len(source_rows) - len(missing_sources),
            "sources_missing": len(missing_sources),
            "sources_missing_layer30_ref": len(missing_layer30_refs),
            "sources_missing_layer20_ref": len(missing_layer20_refs),
            "sources_missing_layer10_ref": len(missing_layer10_refs),
            "lineage_missing_links": len(lineage_missing),
            "internal_links_checked": len(internal_links),
            "internal_links_broken": len(broken_internal_links),
            "external_links_checked": len([l for l in external_links if l.status != "skipped"]),
            "external_links_broken": len(broken_external_links),
            "external_links_stale": len(stale_external_links),
        },
        "lineage_missing": lineage_missing,
        "sources": source_rows,
        "missing_sources": missing_sources,
        "missing_layer_references": {
            "layer30": missing_layer30_refs,
            "layer20": missing_layer20_refs,
            "layer10": missing_layer10_refs,
        },
        "record_results": record_results,
        "links": {
            "internal": [l.__dict__ for l in internal_links],
            "external": [l.__dict__ for l in external_links],
            "broken_internal": [l.__dict__ for l in broken_internal_links],
            "broken_external": [l.__dict__ for l in broken_external_links],
            "stale_external": [l.__dict__ for l in stale_external_links],
        },
    }


def _default_index_input(domain: str) -> Path:
    return Path.cwd() / f"40_index_{domain}"


def _default_wiki_root(domain: str) -> Path:
    return Path.cwd() / f"60_wiki_{domain}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit wiki coverage from 40_index and verify wiki links")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--input", default="", help="Path to 40_index_<domain> folder or index.json")
    parser.add_argument("--output", default="", help="Path to 60_wiki_<domain> folder")
    parser.add_argument("--report", default="", help="Output JSON report path")
    parser.add_argument("--config", default="")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--layer10", default="")
    parser.add_argument("--layer20", default="")
    parser.add_argument("--layer30", default="")
    parser.add_argument("--check-external-links", action="store_true")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--stale-days", type=int, default=730)
    args = parser.parse_args()

    index_input = Path(args.input) if args.input else _default_index_input(args.domain)
    wiki_root = Path(args.output) if args.output else _default_wiki_root(args.domain)

    layer10_root = Path(args.layer10) if args.layer10 else (Path.cwd() / f"10_md_{args.domain}")
    layer20_root = Path(args.layer20) if args.layer20 else (Path.cwd() / f"20_chapter_{args.domain}")
    layer30_root = Path(args.layer30) if args.layer30 else (Path.cwd() / f"30_chunk_{args.domain}")

    if not index_input.exists():
        print(f"input missing: {index_input}")
        return 1
    if not wiki_root.exists():
        print(f"wiki root missing: {wiki_root}")
        return 1

    report = audit_wiki(
        domain=args.domain,
        index_input=index_input,
        wiki_root=wiki_root,
        layer10_root=layer10_root,
        layer20_root=layer20_root,
        layer30_root=layer30_root,
        check_external_links=args.check_external_links,
        timeout_seconds=args.timeout,
        stale_days=args.stale_days,
    )

    report_path = Path(args.report) if args.report else (wiki_root / "wiki_audit_report.json")

    if args.dry_run:
        print(json.dumps(report.get("summary", {}), indent=2, ensure_ascii=False))
    else:
        if report_path.exists() and not args.force:
            print(f"report exists: {report_path} (use --force to overwrite)")
            return 1
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"report={report_path}")
        print(
            "sources_missing={sm} internal_links_broken={ib} external_links_broken={eb} external_links_stale={es}".format(
                sm=report["summary"]["sources_missing"],
                ib=report["summary"]["internal_links_broken"],
                eb=report["summary"]["external_links_broken"],
                es=report["summary"]["external_links_stale"],
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
