from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.pipelines.utils import add_shared_cli_arguments, load_config
from tools.structure.utils import parse_frontmatter


EXIT_SUCCESS = 0
EXIT_STAGE_FAILED = 2
EXIT_CONFIG = 3
EXIT_INTERRUPT = 4


@dataclass(frozen=True)
class SourceStatus:
    md_path: Path
    md_stem: str
    source_id: str
    source_file: str
    status: str
    match_detail: str


def _to_posix(path: Path) -> str:
    return path.as_posix()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _scan_raw(raw_root: Path) -> dict[str, Any]:
    files = [p for p in raw_root.rglob("*") if p.is_file()]
    files = sorted(files, key=lambda p: p.relative_to(raw_root).as_posix().lower())

    by_name: dict[str, list[Path]] = {}
    by_stem: dict[str, list[Path]] = {}
    by_hash: dict[str, list[Path]] = {}
    by_rel: dict[str, Path] = {}

    for path in files:
        rel = path.relative_to(raw_root).as_posix().lower()
        by_rel[rel] = path
        by_name.setdefault(path.name.lower(), []).append(path)
        by_stem.setdefault(path.stem.lower(), []).append(path)
        digest = _sha256(path)
        by_hash.setdefault(digest, []).append(path)

    return {
        "files": files,
        "by_name": by_name,
        "by_stem": by_stem,
        "by_hash": by_hash,
        "by_rel": by_rel,
    }


def _normalize_meta_path(value: str) -> str:
    return value.strip().replace("\\", "/").lstrip("./").lower()


def _detect_sources(layer10_root: Path, raw_index: dict[str, Any]) -> tuple[list[SourceStatus], set[str], set[str], list[dict[str, str]]]:
    statuses: list[SourceStatus] = []
    missing_source_ids: set[str] = set()
    missing_md_stems: set[str] = set()
    rename_hits: list[dict[str, str]] = []

    md_files = [p for p in layer10_root.glob("*.md") if p.is_file() and p.name != "INDEX.md"]
    md_files = sorted(md_files, key=lambda p: p.name.lower())

    for md_path in md_files:
        parsed = parse_frontmatter(md_path.read_text(encoding="utf-8"))
        meta = parsed.metadata
        md_stem = md_path.stem
        source_id = meta.get("source_id") or meta.get("document_id") or md_stem
        source_file = meta.get("source_file", "")
        lineage_layer00 = _normalize_meta_path(meta.get("lineage.layer00_path", ""))
        source_hash = meta.get("hash_sha256", "")

        if lineage_layer00 and lineage_layer00 in raw_index["by_rel"]:
            statuses.append(
                SourceStatus(
                    md_path=md_path,
                    md_stem=md_stem,
                    source_id=source_id,
                    source_file=source_file,
                    status="ok",
                    match_detail="lineage.layer00_path",
                )
            )
            continue

        name_candidates = raw_index["by_name"].get(source_file.lower(), []) if source_file else []
        if len(name_candidates) == 1:
            statuses.append(
                SourceStatus(
                    md_path=md_path,
                    md_stem=md_stem,
                    source_id=source_id,
                    source_file=source_file,
                    status="renamed_or_moved",
                    match_detail="source_file(name)",
                )
            )
            rename_hits.append(
                {
                    "md": _to_posix(md_path),
                    "source_file": source_file,
                    "raw_path": _to_posix(name_candidates[0]),
                    "reason": "name_match",
                }
            )
            continue

        if source_hash:
            hash_candidates = raw_index["by_hash"].get(source_hash, [])
            if len(hash_candidates) == 1:
                statuses.append(
                    SourceStatus(
                        md_path=md_path,
                        md_stem=md_stem,
                        source_id=source_id,
                        source_file=source_file,
                        status="renamed_or_moved",
                        match_detail="hash_sha256",
                    )
                )
                rename_hits.append(
                    {
                        "md": _to_posix(md_path),
                        "source_file": source_file,
                        "raw_path": _to_posix(hash_candidates[0]),
                        "reason": "hash_match",
                    }
                )
                continue

        stem_key = Path(source_file).stem.lower() if source_file else ""
        stem_candidates = raw_index["by_stem"].get(stem_key, []) if stem_key else []
        if len(stem_candidates) == 1:
            statuses.append(
                SourceStatus(
                    md_path=md_path,
                    md_stem=md_stem,
                    source_id=source_id,
                    source_file=source_file,
                    status="renamed_or_moved",
                    match_detail="source_file(stem)",
                )
            )
            rename_hits.append(
                {
                    "md": _to_posix(md_path),
                    "source_file": source_file,
                    "raw_path": _to_posix(stem_candidates[0]),
                    "reason": "stem_match",
                }
            )
            continue

        statuses.append(
            SourceStatus(
                md_path=md_path,
                md_stem=md_stem,
                source_id=source_id,
                source_file=source_file,
                status="missing",
                match_detail="not_found",
            )
        )
        missing_source_ids.add(source_id)
        missing_md_stems.add(md_stem)

    return statuses, missing_source_ids, missing_md_stems, rename_hits


def _remove_path(path: Path, *, dry_run: bool, removed: list[str]) -> None:
    if not path.exists():
        return
    removed.append(path.as_posix())
    if dry_run:
        return
    if path.is_file():
        path.unlink(missing_ok=True)
        return
    for nested in sorted(path.rglob("*"), key=lambda p: len(p.as_posix()), reverse=True):
        if nested.is_file():
            nested.unlink(missing_ok=True)
        elif nested.is_dir():
            try:
                nested.rmdir()
            except OSError:
                pass
    try:
        path.rmdir()
    except OSError:
        pass


def _cleanup_layer10(layer10_root: Path, statuses: list[SourceStatus], *, dry_run: bool, removed: list[str]) -> list[SourceStatus]:
    missing = [s for s in statuses if s.status == "missing"]
    for state in missing:
        _remove_path(state.md_path, dry_run=dry_run, removed=removed)
    return missing


def _cleanup_layer20(layer20_root: Path, missing_md_stems: set[str], *, dry_run: bool, removed: list[str]) -> None:
    if not layer20_root.exists():
        return
    for stem in sorted(missing_md_stems):
        _remove_path(layer20_root / stem, dry_run=dry_run, removed=removed)
        for file_path in layer20_root.glob(f"{stem}_*.md"):
            _remove_path(file_path, dry_run=dry_run, removed=removed)


def _chunk_source_id(path: Path) -> tuple[str, str]:
    parsed = parse_frontmatter(path.read_text(encoding="utf-8"))
    source_id = parsed.metadata.get("source_id") or parsed.metadata.get("document_id", "")
    source_file = parsed.metadata.get("source_file", "")
    return source_id, source_file


def _cleanup_layer30(
    layer30_root: Path,
    *,
    missing_source_ids: set[str],
    missing_md_stems: set[str],
    dry_run: bool,
    removed: list[str],
) -> tuple[set[str], set[str]]:
    if not layer30_root.exists():
        return set(), set()

    removed_chunk_ids: set[str] = set()
    removed_evidence_ids: set[str] = set()

    for candidate_dir in sorted([p for p in layer30_root.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
        remove_dir = candidate_dir.name in missing_source_ids or candidate_dir.name in missing_md_stems
        if not remove_dir:
            chunk_files = sorted(candidate_dir.glob("*.md"), key=lambda p: p.name.lower())
            for chunk_file in chunk_files:
                source_id, _ = _chunk_source_id(chunk_file)
                if source_id in missing_source_ids:
                    remove_dir = True
                    break

        if remove_dir:
            for chunk_file in candidate_dir.glob("*.md"):
                parsed = parse_frontmatter(chunk_file.read_text(encoding="utf-8"))
                chunk_id = parsed.metadata.get("chunk_id")
                if chunk_id:
                    removed_chunk_ids.add(chunk_id)
                    removed_evidence_ids.add(f"evidence_{chunk_id}")
            _remove_path(candidate_dir, dry_run=dry_run, removed=removed)

    return removed_chunk_ids, removed_evidence_ids


def _cleanup_layer40(
    layer40_root: Path,
    *,
    active_source_ids: set[str],
    removed_chunk_ids: set[str],
    removed_evidence_ids: set[str],
    dry_run: bool,
    removed: list[str],
) -> tuple[set[str], set[str], dict[str, int], list[str]]:
    index_path = layer40_root / "index.json"
    topic_dir = layer40_root / "by_topic"
    warnings: list[str] = []

    if not index_path.exists():
        return set(), set(), {"kept": 0, "removed": 0}, warnings

    try:
        records_raw = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        records_raw = []
        warnings.append("invalid_index_json")

    if not isinstance(records_raw, list):
        records_raw = []
        warnings.append("index_not_list")

    kept: list[dict[str, Any]] = []
    removed_count = 0

    for rec in records_raw:
        if not isinstance(rec, dict):
            removed_count += 1
            continue
        source_id = str(rec.get("source_id", ""))
        chunk_id = str(rec.get("chunk_id", ""))
        evidence_id = str(rec.get("evidence_id", ""))

        orphan = False
        if source_id and source_id not in active_source_ids:
            orphan = True
        if chunk_id and chunk_id in removed_chunk_ids:
            orphan = True
        if evidence_id and evidence_id in removed_evidence_ids:
            orphan = True

        if orphan:
            removed_count += 1
            continue
        kept.append(rec)

    kept_chunk_ids = {str(r.get("chunk_id", "")) for r in kept if isinstance(r, dict)}
    kept_evidence_ids = {str(r.get("evidence_id", "")) for r in kept if isinstance(r, dict)}

    if removed_count > 0:
        if dry_run:
            removed.append(index_path.as_posix())
        else:
            index_path.write_text(json.dumps(kept, indent=2, ensure_ascii=False), encoding="utf-8")

    if topic_dir.exists():
        topics: dict[str, list[dict[str, Any]]] = {}
        for rec in kept:
            topic = str(rec.get("topic", "general"))
            topics.setdefault(topic, []).append(rec)

        existing_topic_files = [p for p in topic_dir.glob("*.json") if p.is_file()]
        target_names = {f"{topic}.json" for topic in topics.keys()}

        for existing in existing_topic_files:
            if existing.name not in target_names:
                _remove_path(existing, dry_run=dry_run, removed=removed)

        if not dry_run:
            topic_dir.mkdir(parents=True, exist_ok=True)
            for topic, items in sorted(topics.items(), key=lambda t: t[0]):
                (topic_dir / f"{topic}.json").write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    return kept_chunk_ids, kept_evidence_ids, {"kept": len(kept), "removed": removed_count}, warnings


def _cleanup_layer50_json(
    embedding_json: Path,
    *,
    keep_chunk_ids: set[str],
    keep_evidence_ids: set[str],
    dry_run: bool,
    removed: list[str],
) -> tuple[int, int, list[str]]:
    warnings: list[str] = []
    if not embedding_json.exists():
        return 0, 0, warnings

    try:
        rows_raw = json.loads(embedding_json.read_text(encoding="utf-8"))
    except Exception:
        return 0, 0, ["invalid_embeddings_json"]

    if not isinstance(rows_raw, list):
        return 0, 0, ["embeddings_not_list"]

    kept: list[dict[str, Any]] = []
    removed_count = 0
    for row in rows_raw:
        if not isinstance(row, dict):
            removed_count += 1
            continue
        chunk_id = str(row.get("chunk_id", ""))
        evidence_id = str(row.get("evidence_id", ""))
        if (chunk_id and chunk_id in keep_chunk_ids) or (evidence_id and evidence_id in keep_evidence_ids):
            kept.append(row)
        else:
            removed_count += 1

    if removed_count > 0:
        if dry_run:
            removed.append(embedding_json.as_posix())
        else:
            embedding_json.write_text(json.dumps(kept, indent=2, ensure_ascii=False), encoding="utf-8")

    return len(kept), removed_count, warnings


def _cleanup_layer50_sqlite(
    db_path: Path,
    *,
    keep_chunk_ids: set[str],
    keep_evidence_ids: set[str],
    dry_run: bool,
) -> tuple[int, int, list[str]]:
    warnings: list[str] = []
    if not db_path.exists():
        return 0, 0, warnings

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        try:
            rows = cur.execute("SELECT embedding_id, chunk_id, evidence_id FROM embeddings").fetchall()
        except sqlite3.Error:
            return 0, 0, ["sqlite_missing_embeddings_table"]

        remove_ids: list[str] = []
        keep_count = 0
        for embedding_id, chunk_id, evidence_id in rows:
            c = str(chunk_id or "")
            e = str(evidence_id or "")
            if (c and c in keep_chunk_ids) or (e and e in keep_evidence_ids):
                keep_count += 1
                continue
            remove_ids.append(str(embedding_id))

        if remove_ids and not dry_run:
            cur.executemany("DELETE FROM embeddings WHERE embedding_id = ?", [(i,) for i in remove_ids])
            conn.commit()

        return keep_count, len(remove_ids), warnings
    finally:
        conn.close()


def run_cleanup(*, domain: str, output_root: Path, dry_run: bool = False) -> dict[str, Any]:
    raw_root = output_root / f"00_raw_{domain}"
    layer10_root = output_root / f"10_md_{domain}"
    layer20_root = output_root / f"20_chapter_{domain}"
    layer30_root = output_root / f"30_chunk_{domain}"
    layer40_root = output_root / f"40_index_{domain}"
    layer50_root = output_root / f"50_embedding_{domain}"

    if not raw_root.exists():
        return {
            "status": "failed",
            "domain": domain,
            "errors": [f"raw_input_missing:{raw_root.as_posix()}"],
        }

    removed_paths: list[str] = []
    warnings: list[str] = []

    raw_index = _scan_raw(raw_root)
    statuses, missing_source_ids, missing_md_stems, rename_hits = _detect_sources(layer10_root, raw_index)

    _cleanup_layer10(layer10_root, statuses, dry_run=dry_run, removed=removed_paths)
    _cleanup_layer20(layer20_root, missing_md_stems, dry_run=dry_run, removed=removed_paths)
    removed_chunk_ids, removed_evidence_ids = _cleanup_layer30(
        layer30_root,
        missing_source_ids=missing_source_ids,
        missing_md_stems=missing_md_stems,
        dry_run=dry_run,
        removed=removed_paths,
    )

    active_source_ids = {s.source_id for s in statuses if s.status != "missing"}
    keep_chunk_ids, keep_evidence_ids, index_counts, index_warnings = _cleanup_layer40(
        layer40_root,
        active_source_ids=active_source_ids,
        removed_chunk_ids=removed_chunk_ids,
        removed_evidence_ids=removed_evidence_ids,
        dry_run=dry_run,
        removed=removed_paths,
    )
    warnings.extend(index_warnings)

    emb_json_keep, emb_json_removed, emb_json_warnings = _cleanup_layer50_json(
        layer50_root / "embeddings.json",
        keep_chunk_ids=keep_chunk_ids,
        keep_evidence_ids=keep_evidence_ids,
        dry_run=dry_run,
        removed=removed_paths,
    )
    warnings.extend(emb_json_warnings)

    emb_sqlite_keep, emb_sqlite_removed, emb_sqlite_warnings = _cleanup_layer50_sqlite(
        layer50_root / "embeddings.db",
        keep_chunk_ids=keep_chunk_ids,
        keep_evidence_ids=keep_evidence_ids,
        dry_run=dry_run,
    )
    warnings.extend(emb_sqlite_warnings)

    report = {
        "status": "ok",
        "domain": domain,
        "dry_run": dry_run,
        "paths": {
            "raw": raw_root.as_posix(),
            "layer10": layer10_root.as_posix(),
            "layer20": layer20_root.as_posix(),
            "layer30": layer30_root.as_posix(),
            "layer40": layer40_root.as_posix(),
            "layer50": layer50_root.as_posix(),
        },
        "summary": {
            "raw_files": len(raw_index["files"]),
            "layer10_documents": len(statuses),
            "missing_primary_sources": len(missing_source_ids),
            "renamed_or_moved_matches": len(rename_hits),
            "removed_paths": len(removed_paths),
            "layer40_removed_records": index_counts["removed"],
            "layer40_kept_records": index_counts["kept"],
            "layer50_removed_embeddings_json": emb_json_removed,
            "layer50_kept_embeddings_json": emb_json_keep,
            "layer50_removed_embeddings_sqlite": emb_sqlite_removed,
            "layer50_kept_embeddings_sqlite": emb_sqlite_keep,
        },
        "missing_sources": sorted(missing_source_ids),
        "renamed_or_moved": rename_hits,
        "removed": sorted(set(removed_paths)),
        "warnings": sorted(set(warnings)),
        "errors": [],
    }
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cleanup orphaned derived artifacts when raw sources are missing")
    add_shared_cli_arguments(parser)
    return parser


def main() -> int:
    try:
        args = _parser().parse_args()
        _ = load_config(args.config)

        output_root = Path(args.output) if args.output else Path.cwd()
        report_path = (
            Path(args.report)
            if args.report
            else output_root / f"pipeline_cleanup_{args.domain}.json"
        )

        report = run_cleanup(domain=args.domain, output_root=output_root, dry_run=args.dry_run)

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")

        if report["status"] != "ok":
            print(f"status=failed errors={len(report.get('errors', []))}")
            return EXIT_CONFIG

        summary = report["summary"]
        print(
            "status=ok missing_sources={missing} removed_paths={removed} removed_index={idx} removed_embeddings={emb}".format(
                missing=summary["missing_primary_sources"],
                removed=summary["removed_paths"],
                idx=summary["layer40_removed_records"],
                emb=summary["layer50_removed_embeddings_json"] + summary["layer50_removed_embeddings_sqlite"],
            )
        )
        return EXIT_SUCCESS if not report["errors"] else EXIT_STAGE_FAILED
    except KeyboardInterrupt:
        return EXIT_INTERRUPT
    except Exception:
        return EXIT_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())