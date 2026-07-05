from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.pipelines.utils import add_shared_cli_arguments, load_config


EXIT_NO_CHANGES = 0
EXIT_CHANGES_DETECTED = 1
EXIT_CONFIG = 3
EXIT_INTERRUPT = 4


def _manifest_path(output_root: Path, domain: str) -> Path:
    return output_root / ".pipeline_state" / f"source_manifest_{domain}.json"


def _default_report_path(output_root: Path, domain: str) -> Path:
    return output_root / ".pipeline_state" / f"source_change_{domain}.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _scan_files(input_path: Path) -> list[Path]:
    files = [p for p in input_path.rglob("*") if p.is_file()]
    return sorted(files, key=lambda p: p.relative_to(input_path).as_posix().lower())


def _build_manifest(input_path: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for file_path in _scan_files(input_path):
        rel = file_path.relative_to(input_path).as_posix()
        manifest[rel] = _sha256(file_path)
    return manifest


def _load_manifest(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, str):
            out[key] = value
    return out


def write_manifest(*, output_root: Path, domain: str, manifest: dict[str, str]) -> Path:
    path = _manifest_path(output_root, domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    stable = {k: manifest[k] for k in sorted(manifest.keys())}
    path.write_text(json.dumps(stable, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def write_change_report(report: dict[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    stable_report = {
        "status": report["status"],
        "changes_detected": report["changes_detected"],
        "new_files": sorted(report["new_files"]),
        "modified_files": sorted(report["modified_files"]),
        "removed_files": sorted(report["removed_files"]),
        "unchanged_files": sorted(report["unchanged_files"]),
        "summary": report["summary"],
        "domain": report["domain"],
        "input": report["input"],
    }
    report_path.write_text(json.dumps(stable_report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def detect_source_changes(*, domain: str, input_path: Path, output_root: Path) -> dict[str, Any]:
    current_manifest = _build_manifest(input_path)
    previous_manifest = _load_manifest(_manifest_path(output_root, domain))

    current_keys = set(current_manifest.keys())
    previous_keys = set(previous_manifest.keys())

    new_files = sorted(current_keys - previous_keys)
    removed_files = sorted(previous_keys - current_keys)

    common = sorted(current_keys & previous_keys)
    modified_files = sorted([k for k in common if current_manifest[k] != previous_manifest[k]])
    unchanged_files = sorted([k for k in common if current_manifest[k] == previous_manifest[k]])

    changes_detected = bool(new_files or modified_files or removed_files)
    status = "changes_detected" if changes_detected else "no_changes"

    report: dict[str, Any] = {
        "status": status,
        "changes_detected": changes_detected,
        "new_files": new_files,
        "modified_files": modified_files,
        "removed_files": removed_files,
        "unchanged_files": unchanged_files,
        "summary": {
            "total_current_files": len(current_manifest),
            "total_previous_files": len(previous_manifest),
            "new_count": len(new_files),
            "modified_count": len(modified_files),
            "removed_count": len(removed_files),
            "unchanged_count": len(unchanged_files),
        },
        "domain": domain,
        "input": input_path.as_posix(),
        "current_manifest": current_manifest,
    }
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic source change detector for incremental pipeline")
    add_shared_cli_arguments(parser)
    return parser


def main() -> int:
    try:
        args = _parser().parse_args()
        _ = load_config(args.config)

        input_path = Path(args.input) if args.input else (Path.cwd() / f"00_raw_{args.domain}")
        output_root = Path(args.output) if args.output else Path.cwd()
        report_path = Path(args.report) if args.report else _default_report_path(output_root, args.domain)

        if not input_path.exists():
            print(f"input missing: {input_path}")
            return EXIT_CONFIG

        result = detect_source_changes(domain=args.domain, input_path=input_path, output_root=output_root)
        write_change_report(result, report_path)

        if not args.dry_run:
            write_manifest(output_root=output_root, domain=args.domain, manifest=result["current_manifest"])

        print(
            "status={status} changes={changes} new={new} modified={modified} removed={removed} unchanged={unchanged}".format(
                status=result["status"],
                changes=str(result["changes_detected"]).lower(),
                new=len(result["new_files"]),
                modified=len(result["modified_files"]),
                removed=len(result["removed_files"]),
                unchanged=len(result["unchanged_files"]),
            )
        )

        return EXIT_CHANGES_DETECTED if result["changes_detected"] else EXIT_NO_CHANGES
    except KeyboardInterrupt:
        return EXIT_INTERRUPT
    except Exception:
        return EXIT_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())
