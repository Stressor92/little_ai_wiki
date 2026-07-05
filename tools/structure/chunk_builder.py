from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import time

from tools.structure.chunk_metadata import build_chunk_metadata
from tools.structure.chunk_report import ChunkRunReport, write_report
from tools.structure.chunk_rules import ChunkRulesConfig, plan_chunks
from tools.structure.chunk_validator import validate_chunk_metadata, validate_document_ordering
from tools.structure.chunk_writer import chunk_output_path, render_chunk_markdown
from tools.structure.token_counter import count_tokens
from tools.structure.utils import deterministic_files, parse_frontmatter


@dataclass(frozen=True)
class ChapterFile:
    file_path: Path
    metadata: dict[str, str]
    body: str


def _discover_chapters(input_path: Path, recursive: bool) -> list[Path]:
    files = deterministic_files(input_path, recursive=recursive)
    return [
        f
        for f in files
        if f.suffix.lower() == ".md"
        and f.name != "INDEX.md"
        and not f.name.lower().endswith("_toc.md")
        and "index" not in {part.lower() for part in f.parts}
    ]


def _load_chapter(path: Path) -> ChapterFile:
    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    if not fm.metadata:
        raise ValueError("frontmatter missing")
    if "chapter_id" not in fm.metadata and "chapter" not in fm.metadata:
        raise ValueError("chapter id missing")
    return ChapterFile(file_path=path, metadata=fm.metadata, body=fm.body)


def _write_manifest(manifest_path: Path, entries: list[dict]) -> None:
    import json

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def run_chunk_builder(
    *,
    domain: str,
    input_path: Path,
    output_path: Path,
    topic: str,
    target_tokens: int,
    minimum_tokens: int,
    maximum_tokens: int,
    recursive: bool,
    force: bool,
    dry_run: bool,
    flat_output: bool,
    split_tables: bool,
    split_code_blocks: bool,
    preserve_headings: bool,
    write_manifest: bool,
    report_path: Path | None,
) -> ChunkRunReport:
    started = time.monotonic()
    report = ChunkRunReport()
    cfg = ChunkRulesConfig(
        target_tokens=target_tokens,
        minimum_tokens=minimum_tokens,
        maximum_tokens=maximum_tokens,
        split_tables=split_tables,
        split_code_blocks=split_code_blocks,
        preserve_headings=preserve_headings,
    )

    chapter_paths = _discover_chapters(input_path, recursive=recursive)
    token_sizes: list[int] = []
    manifest_entries: list[dict] = []
    global_ids: set[str] = set()

    report.stats["chapters_processed"] = len(chapter_paths)

    docs_seen: set[str] = set()

    for chapter_path in chapter_paths:
        key = chapter_path.parent.as_posix()
        docs_seen.add(key)

        try:
            chapter = _load_chapter(chapter_path)
            chunks = plan_chunks(chapter.body, cfg)
            stable_ts = datetime.fromtimestamp(chapter_path.stat().st_mtime, tz=timezone.utc).isoformat()

            chunk_metas: list[dict] = []
            for i, chunk in enumerate(chunks, start=1):
                meta = build_chunk_metadata(
                    chapter_meta=chapter.metadata,
                    chunk_content=chunk.content,
                    domain=domain,
                    topic=topic,
                    chapter_file=chapter.file_path,
                    sequence=i,
                    token_count=chunk.token_count,
                    paragraph_start=chunk.paragraph_start,
                    paragraph_end=chunk.paragraph_end,
                    created_at=stable_ts,
                    updated_at=stable_ts,
                ).values

                chunk_id = str(meta["chunk_id"])
                if chunk_id in global_ids:
                    raise RuntimeError(f"duplicate chunk id detected: {chunk_id}")
                global_ids.add(chunk_id)

                validation = validate_chunk_metadata(meta, minimum_tokens, maximum_tokens)
                if validation.errors:
                    report.errors.setdefault(chapter_path.as_posix(), []).extend(validation.errors)
                    continue
                if validation.warnings:
                    report.warnings.setdefault(chapter_path.as_posix(), []).extend(validation.warnings)

                document_id = str(meta["document_id"])
                out_path = chunk_output_path(output_path, document_id, i, flat=flat_output)
                markdown = render_chunk_markdown(meta, chunk.content)
                token_sizes.append(count_tokens(chunk.content))

                if write_manifest:
                    manifest_entries.append({
                        "chunk_id": chunk_id,
                        "output_file": out_path.as_posix(),
                        "chapter_file": chapter_path.as_posix(),
                        "token_count": meta["token_count"],
                    })

                if dry_run:
                    report.skipped_chunks.append(out_path.as_posix())
                else:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    if out_path.exists() and not force:
                        report.skipped_chunks.append(out_path.as_posix())
                    else:
                        previous = out_path.read_text(encoding="utf-8") if out_path.exists() else None
                        out_path.write_text(markdown, encoding="utf-8")
                        if previous is None:
                            report.created_chunks.append(out_path.as_posix())
                        elif previous != markdown:
                            report.updated_chunks.append(out_path.as_posix())
                        else:
                            report.skipped_chunks.append(out_path.as_posix())

                chunk_metas.append(meta)

            per_doc_validation = validate_document_ordering(chunk_metas)
            if per_doc_validation.errors:
                report.errors.setdefault(chapter_path.as_posix(), []).extend(per_doc_validation.errors)
            if per_doc_validation.warnings:
                report.warnings.setdefault(chapter_path.as_posix(), []).extend(per_doc_validation.warnings)

        except Exception as exc:  # noqa: BLE001
            report.errors.setdefault(chapter_path.as_posix(), []).append(str(exc))

    report.stats["documents_processed"] = len(docs_seen)
    report.stats["chunks_created"] = len(report.created_chunks) + len(report.updated_chunks)
    report.finalize_chunk_stats(token_sizes)
    report.validation = {
        "duplicate_chunk_ids": False,
        "has_errors": bool(report.errors),
    }
    report.execution_time = round(time.monotonic() - started, 4)

    if write_manifest and not dry_run:
        _write_manifest(output_path / "chunk_manifest.json", manifest_entries)

    if report_path is not None:
        write_report(report_path, report)

    return report


def _default_input(domain: str) -> Path:
    return Path.cwd() / f"20_chapter_{domain}"


def _default_output(domain: str) -> Path:
    return Path.cwd() / f"30_chunk_{domain}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic chunk builder: 20_chapter_* -> 30_chunk_*")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--input", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--topic", default="general")
    parser.add_argument("--target-tokens", type=int, default=300)
    parser.add_argument("--minimum-tokens", type=int, default=100)
    parser.add_argument("--maximum-tokens", type=int, default=500)
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", default="")
    parser.add_argument("--flat", action="store_true")
    parser.add_argument("--split-tables", action="store_true")
    parser.add_argument("--split-code-blocks", action="store_true")
    parser.add_argument("--preserve-headings", action="store_true", default=True)
    parser.add_argument("--no-preserve-headings", dest="preserve_headings", action="store_false")
    parser.add_argument("--write-manifest", action="store_true", default=True)
    parser.add_argument("--no-write-manifest", dest="write_manifest", action="store_false")

    args = parser.parse_args()

    report = run_chunk_builder(
        domain=args.domain,
        input_path=Path(args.input) if args.input else _default_input(args.domain),
        output_path=Path(args.output) if args.output else _default_output(args.domain),
        topic=args.topic,
        target_tokens=args.target_tokens,
        minimum_tokens=args.minimum_tokens,
        maximum_tokens=args.maximum_tokens,
        recursive=args.recursive,
        force=args.force,
        dry_run=args.dry_run,
        flat_output=args.flat,
        split_tables=args.split_tables,
        split_code_blocks=args.split_code_blocks,
        preserve_headings=args.preserve_headings,
        write_manifest=args.write_manifest,
        report_path=Path(args.report) if args.report else None,
    )

    print(
        "created={c} updated={u} skipped={s} warnings={w} errors={e}".format(
            c=len(report.created_chunks),
            u=len(report.updated_chunks),
            s=len(report.skipped_chunks),
            w=sum(len(v) for v in report.warnings.values()),
            e=sum(len(v) for v in report.errors.values()),
        )
    )

    return 0 if not report.errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
