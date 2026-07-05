from __future__ import annotations

import argparse
from pathlib import Path
import json
import hashlib


def add_shared_cli_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--domain", required=True)
    parser.add_argument("--input", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--report", default="")
    parser.add_argument("--config", default="")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--verbose", action="store_true")


def load_config(path: str) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config not found: {p}")
    if p.suffix.lower() == ".json":
        return json.loads(p.read_text(encoding="utf-8"))
    raise ValueError("only JSON config files are supported")


def path_checksum(path: Path) -> str:
    h = hashlib.sha256()
    if not path.exists():
        return "missing"
    if path.is_file():
        h.update(path.read_bytes())
        return h.hexdigest()

    files = sorted([p for p in path.rglob("*") if p.is_file()], key=lambda p: p.as_posix().lower())
    for f in files:
        rel = f.relative_to(path).as_posix().encode("utf-8")
        h.update(rel)
        h.update(f.read_bytes())
    return h.hexdigest()


def stable_execution_id(pipeline: str, domain: str, config: dict) -> str:
    payload = json.dumps({"pipeline": pipeline, "domain": domain, "config": config}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
