from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re


REQUIRED_FRONTMATTER = [
    "document_id",
    "source_id",
    "domain",
    "topic",
    "source_file",
    "source_format",
    "created_at",
    "updated_at",
    "hash_sha256",
    "lineage.layer00_path",
]


@dataclass
class NormalizeResult:
    text: str
    warnings: list[str]
    changed: bool


def _split_frontmatter(text: str) -> tuple[dict[str, str], str, bool]:
    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].strip() == "---":
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end is not None:
            fm_lines = lines[1:end]
            body = "\n".join(lines[end + 1 :])
            fm: dict[str, str] = {}
            for line in fm_lines:
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"')
            return fm, body, True
    return {}, text, False


def _build_frontmatter(fm: dict[str, str]) -> str:
    ordered = [k for k in REQUIRED_FRONTMATTER if k in fm] + [
        k for k in sorted(fm.keys()) if k not in REQUIRED_FRONTMATTER
    ]
    lines = ["---"]
    for key in ordered:
        val = fm[key]
        lines.append(f'{key}: "{val}"')
    lines.append("---")
    return "\n".join(lines)


def _normalize_body(body: str, fallback_h1: str) -> tuple[str, list[str]]:
    warnings: list[str] = []

    body = body.replace("\r\n", "\n").replace("\r", "\n")

    # Preserve fenced code blocks, normalize only outside.
    lines = body.split("\n")
    out: list[str] = []
    in_fence = False

    h1_count = 0
    for raw in lines:
        line = raw.rstrip()

        if line.strip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue

        if not in_fence:
            line = re.sub(r"\s+$", "", line)
            line = re.sub(r"^(#{1,6})([^\s#])", r"\1 \2", line)

            if line.startswith("# "):
                h1_count += 1
                if h1_count > 1:
                    line = "## " + line[2:]

        out.append(line)

    if h1_count == 0:
        out.insert(0, f"# {fallback_h1}")
        out.insert(1, "")
        warnings.append("Inserted missing H1 heading.")

    # Collapse >2 empty lines.
    collapsed: list[str] = []
    blank_count = 0
    for line in out:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                collapsed.append("")
        else:
            blank_count = 0
            collapsed.append(line)

    result = "\n".join(collapsed).strip() + "\n"

    if "[source" not in result.lower() and "source_id" not in result.lower():
        warnings.append("No source markers found in body.")

    return result, warnings


def normalize_markdown(
    text: str,
    *,
    domain: str,
    topic: str,
    source_file: str,
    source_format: str,
    source_hash: str,
    lineage_path: str,
    fallback_document_id: str,
    stable_timestamp: str,
) -> NormalizeResult:
    original = text
    warnings: list[str] = []

    fm, body, has_fm = _split_frontmatter(text)
    if not has_fm:
        warnings.append("Missing frontmatter; created new frontmatter block.")

    if not fm.get("document_id"):
        fm["document_id"] = fallback_document_id
    if not fm.get("source_id"):
        fm["source_id"] = fallback_document_id
    fm["domain"] = domain
    fm["topic"] = topic or "general"
    fm["source_file"] = source_file
    fm["source_format"] = source_format.lower().lstrip(".")
    fm.setdefault("created_at", stable_timestamp)
    fm["updated_at"] = stable_timestamp
    fm["hash_sha256"] = source_hash
    fm["lineage.layer00_path"] = lineage_path

    norm_body, body_warnings = _normalize_body(body, fallback_document_id)
    warnings.extend(body_warnings)

    normalized = _build_frontmatter(fm) + "\n\n" + norm_body
    changed = normalized != original

    return NormalizeResult(text=normalized, warnings=warnings, changed=changed)


def _collect_md_files(input_path: Path, recursive: bool) -> list[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() == ".md" else []
    pattern = "**/*.md" if recursive else "*.md"
    return sorted(input_path.glob(pattern))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize markdown files for layer 10 ingest")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--topic", default="general")
    parser.add_argument("--output", default="")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_root = Path(args.output) if args.output else None

    files = _collect_md_files(input_path, recursive=args.recursive)
    report = {
        "changed": [],
        "unchanged": [],
        "warnings": {},
        "errors": {},
    }

    for file_path in files:
        try:
            raw = file_path.read_text(encoding="utf-8")
            stable_ts = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc).isoformat()
            fallback_id = file_path.stem.lower().replace(" ", "_")
            result = normalize_markdown(
                raw,
                domain=args.domain,
                topic=args.topic,
                source_file=file_path.name,
                source_format=file_path.suffix,
                source_hash=_sha256(file_path),
                lineage_path=str(file_path),
                fallback_document_id=fallback_id,
                stable_timestamp=stable_ts,
            )

            if result.warnings:
                report["warnings"][str(file_path)] = result.warnings

            if output_root:
                out_file = output_root / file_path.name
            else:
                out_file = file_path

            if result.changed:
                if args.dry_run:
                    report["changed"].append(str(file_path))
                else:
                    if out_file.exists() and not args.force and out_file != file_path:
                        report["errors"][str(file_path)] = "Output exists; use --force."
                        continue
                    out_file.parent.mkdir(parents=True, exist_ok=True)
                    out_file.write_text(result.text, encoding="utf-8")
                    report["changed"].append(str(file_path))
            else:
                report["unchanged"].append(str(file_path))
        except Exception as exc:  # noqa: BLE001
            report["errors"][str(file_path)] = str(exc)

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        "changed={changed} unchanged={unchanged} warnings={warnings} errors={errors}".format(
            changed=len(report["changed"]),
            unchanged=len(report["unchanged"]),
            warnings=len(report["warnings"]),
            errors=len(report["errors"]),
        )
    )

    return 0 if not report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
