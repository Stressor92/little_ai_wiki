from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Iterable

from tools.ingest.markdown_normalizer import normalize_markdown
from tools.ingest.pptx_conv import convert_pptx_to_markdown
from tools.ingest.xml_conv import convert_xml_to_markdown
from tools.ingest.converters import get_converter, supported_extensions
from tools.ingest.converters.base import MarkdownWriter


CONVERTER_EXTS = set(supported_extensions())
EXTRA_EXTS = {".pptx", ".xml"}
ALL_SUPPORTED = CONVERTER_EXTS | EXTRA_EXTS


@dataclass
class SourceItem:
    path: Path
    rel_path: Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _slug(value: str) -> str:
    return "_".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())


def _discover(input_path: Path, recursive: bool, formats: set[str] | None) -> list[SourceItem]:
    if input_path.is_file():
        ext = input_path.suffix.lower()
        if ext in ALL_SUPPORTED and (formats is None or ext in formats):
            return [SourceItem(path=input_path, rel_path=Path(input_path.name))]
        return []

    pattern = "**/*" if recursive else "*"
    found: list[SourceItem] = []
    for p in sorted(input_path.glob(pattern)):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext not in ALL_SUPPORTED:
            continue
        if formats is not None and ext not in formats:
            continue
        found.append(SourceItem(path=p, rel_path=p.relative_to(input_path)))
    return found


def _convert_source_to_markdown_text(source_path: Path) -> str:
    ext = source_path.suffix.lower()
    if ext == ".pptx":
        return convert_pptx_to_markdown(source_path)
    if ext == ".xml":
        return convert_xml_to_markdown(source_path)

    converter = get_converter(source_path)
    doc = converter.convert(source_path)
    writer = MarkdownWriter(add_toc=True, add_frontmatter=True)
    return writer.render(doc)


def _sectionize(markdown_text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_title = "document"
    buf: list[str] = []

    for line in markdown_text.splitlines():
        if line.startswith("# ") and buf:
            sections.append((current_title, "\n".join(buf).strip() + "\n"))
            current_title = line[2:].strip() or "section"
            buf = [line]
        else:
            if line.startswith("# "):
                current_title = line[2:].strip() or "section"
            buf.append(line)

    if buf:
        sections.append((current_title, "\n".join(buf).strip() + "\n"))
    return sections


def run_ingest(
    *,
    domain: str,
    input_path: Path,
    output_root: Path,
    topic: str,
    recursive: bool,
    formats: set[str] | None,
    dry_run: bool,
    force: bool,
    with_sections: bool,
    report_path: Path | None,
) -> dict:
    discovered = _discover(input_path, recursive=recursive, formats=formats)

    stem_counts: dict[tuple[str, str], int] = {}
    for item in discovered:
        doc_stem = _slug(item.path.stem)
        rel_parent = item.rel_path.parent
        source_slug = _slug(str(rel_parent)) if str(rel_parent) not in ("", ".") else "source"
        key = (source_slug, doc_stem)
        stem_counts[key] = stem_counts.get(key, 0) + 1

    report = {
        "domain": domain,
        "topic": topic,
        "input": str(input_path),
        "output": str(output_root),
        "discovered": len(discovered),
        "changed": [],
        "skipped": [],
        "warnings": {},
        "errors": {},
        "stats": {"bytes_in": 0, "bytes_out": 0},
    }

    for item in discovered:
        src = item.path
        try:
            report["stats"]["bytes_in"] += src.stat().st_size
            doc_stem = _slug(src.stem)
            rel_parent = item.rel_path.parent
            source_slug = _slug(str(rel_parent)) if str(rel_parent) not in ("", ".") else "source"
            key = (source_slug, doc_stem)
            if stem_counts.get(key, 0) > 1:
                ext_slug = _slug(src.suffix.lstrip(".")) or "file"
                out_name = f"{source_slug}_{doc_stem}_{ext_slug}.md"
                fallback_id = _slug(f"{domain}_{source_slug}_{doc_stem}_{ext_slug}")
            else:
                out_name = f"{source_slug}_{doc_stem}.md"
                fallback_id = _slug(f"{domain}_{source_slug}_{doc_stem}")
            out_file = output_root / out_name

            if out_file.exists() and not force and not dry_run:
                report["skipped"].append(str(src))
                continue

            raw_md = _convert_source_to_markdown_text(src)

            stable_ts = datetime.fromtimestamp(src.stat().st_mtime, tz=timezone.utc).isoformat()
            source_hash = _sha256(src)
            normalized = normalize_markdown(
                raw_md,
                domain=domain,
                topic=topic,
                source_file=src.name,
                source_format=src.suffix,
                source_hash=source_hash,
                lineage_path=str(src),
                fallback_document_id=fallback_id,
                stable_timestamp=stable_ts,
            )

            if normalized.warnings:
                report["warnings"][str(src)] = normalized.warnings

            if dry_run:
                report["changed"].append(str(src))
                continue

            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(normalized.text, encoding="utf-8")
            report["stats"]["bytes_out"] += out_file.stat().st_size
            report["changed"].append(str(src))

            if with_sections:
                sections = _sectionize(normalized.text)
                sec_root = output_root / fallback_id / "sections"
                sec_root.mkdir(parents=True, exist_ok=True)
                for idx, (title, content) in enumerate(sections, start=1):
                    sec_name = f"{idx:02d}_{_slug(title)[:80] or 'section'}.md"
                    (sec_root / sec_name).write_text(content, encoding="utf-8")

        except Exception as exc:  # noqa: BLE001
            report["errors"][str(src)] = str(exc)

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return report


def _parse_formats(values: Iterable[str] | None) -> set[str] | None:
    if not values:
        return None
    fmts = set()
    for v in values:
        vv = v.strip().lower()
        if not vv:
            continue
        if not vv.startswith("."):
            vv = "." + vv
        fmts.add(vv)
    return fmts


def main() -> int:
    parser = argparse.ArgumentParser(description="Universal ingest pipeline: 00_raw_* -> 10_md_*")
    parser.add_argument("--domain", default="")
    parser.add_argument("--input", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--topic", default="general")
    parser.add_argument("--formats", nargs="*", default=None)
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--with-sections", action="store_true")
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    if not args.input and not args.domain:
        raise SystemExit("Either --input or --domain is required.")

    if args.input:
        input_path = Path(args.input)
    else:
        input_path = Path.cwd() / f"00_raw_{args.domain}"

    if not args.domain:
        if input_path.name.startswith("00_raw_"):
            domain = input_path.name.replace("00_raw_", "", 1)
        else:
            raise SystemExit("--domain is required when --input is not a 00_raw_<domain> folder.")
    else:
        domain = args.domain

    if args.output:
        output_root = Path(args.output)
    else:
        output_root = Path.cwd() / f"10_md_{domain}"

    report = run_ingest(
        domain=domain,
        input_path=input_path,
        output_root=output_root,
        topic=args.topic,
        recursive=args.recursive,
        formats=_parse_formats(args.formats),
        dry_run=args.dry_run,
        force=args.force,
        with_sections=args.with_sections,
        report_path=Path(args.report) if args.report else None,
    )

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
