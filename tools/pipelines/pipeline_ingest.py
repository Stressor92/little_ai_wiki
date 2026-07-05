from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import time
import traceback
from typing import Dict, List, Tuple

from tools.structure.chunk_builder import run_chunk_builder


# =========================
# CONFIG
# =========================

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

RAW_PREFIX = "00_raw_"
MD_PREFIX = "10_md_"
CHAPTER_PREFIX = "20_chapter_"
CHUNK_PREFIX = "30_chunk_"


# =========================
# DATA MODEL
# =========================

@dataclass
class FileMeta:
    filename: str
    source_extension: str
    source_size_bytes: int
    created: str
    modified: str
    layer1_exists: bool
    layer2_exists: bool
    layer3_exists: bool


@dataclass
class DomainStats:
    domain: str
    scanned_files: int = 0
    md_created: int = 0
    chapter_created: int = 0
    chunk_created: int = 0
    index_updated: int = 0
    errors: int = 0


# =========================
# UTILITIES
# =========================

def now_iso() -> str:
    return datetime.utcnow().isoformat()


def log(msg: str, indent: int = 0):
    print("  " * indent + msg)


def log_error(domain: str, err: Exception):
    print(f"[ERROR] Domain={domain}: {err}")
    traceback.print_exc()


def safe_mkdir(path: Path) -> bool:
    try:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            return True
    except Exception:
        raise
    return False


def safe_touch(path: Path) -> bool:
    try:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")
            return True
    except Exception:
        raise
    return False


# =========================
# DOMAIN DISCOVERY (VARIANT A)
# =========================

def discover_domains(root: Path) -> List[str]:
    domains = []
    for p in root.iterdir():
        if p.is_dir() and p.name.startswith(RAW_PREFIX):
            domains.append(p.name.replace(RAW_PREFIX, ""))
    return sorted(domains)


def get_raw_folder(domain: str) -> Path:
    return WORKSPACE_ROOT / f"{RAW_PREFIX}{domain}"


def get_md_folder(domain: str) -> Path:
    return WORKSPACE_ROOT / f"{MD_PREFIX}{domain}"


def get_chapter_folder(domain: str) -> Path:
    return WORKSPACE_ROOT / f"{CHAPTER_PREFIX}{domain}"


def get_chunk_folder(domain: str) -> Path:
    return WORKSPACE_ROOT / f"{CHUNK_PREFIX}{domain}"


# =========================
# SCANNING
# =========================

def scan_raw_files(domain: str) -> List[Path]:
    raw_path = get_raw_folder(domain)
    if not raw_path.exists():
        return []
    return [f for f in raw_path.iterdir() if f.is_file()]


# =========================
# ENSURE LAYERS
# =========================

def ensure_markdown_file(domain: str, filename: str) -> bool:
    md_path = get_md_folder(domain) / f"{filename}.md"
    return safe_touch(md_path)


def ensure_chapter_folder(domain: str, filename: str) -> bool:
    return safe_mkdir(get_chapter_folder(domain) / filename)


def ensure_chunk_folder(domain: str, filename: str) -> bool:
    return safe_mkdir(get_chunk_folder(domain) / filename)


# =========================
# METADATA
# =========================

def collect_metadata(domain: str, file: Path) -> FileMeta:
    filename = file.stem
    stat = file.stat()

    md = get_md_folder(domain) / f"{filename}.md"
    ch = get_chapter_folder(domain) / filename
    cu = get_chunk_folder(domain) / filename

    return FileMeta(
        filename=filename,
        source_extension=file.suffix,
        source_size_bytes=stat.st_size,
        created=datetime.fromtimestamp(stat.st_ctime).isoformat(),
        modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        layer1_exists=md.exists(),
        layer2_exists=ch.exists(),
        layer3_exists=cu.exists(),
    )


# =========================
# INDEX GENERATION
# =========================

def generate_tree_view(path: Path) -> str:
    lines = []

    def walk(dir_path: Path, prefix: str = ""):
        items = sorted(dir_path.iterdir(), key=lambda x: x.name)
        for i, item in enumerate(items):
            connector = "└── " if i == len(items) - 1 else "├── "
            lines.append(prefix + connector + item.name)
            if item.is_dir():
                walk(item, prefix + ("    " if i == len(items) - 1 else "│   "))

    walk(path)
    return "\n".join(lines)


def layer_to_index(domain: str, layer: int, folder: Path, metas: List[FileMeta]) -> str:
    ts = now_iso()

    header = f"""---
type: index
layer: {layer}
domain: {domain}
folder: {folder.name}
version: 1.0
last_updated: {ts}
---

# INDEX

Domain: {domain}
Layer: {folder.name}
"""

    # Related layers
    if layer == 10:
        related = """## Related Layers

Previous:
- ../00_raw_{domain}

Next:
- ../20_chapter_{domain}
"""
    elif layer == 20:
        related = """## Related Layers

Previous:
- ../10_md_{domain}

Next:
- ../30_chunk_{domain}
"""
    else:
        related = """## Related Layers

Previous:
- ../20_chapter_{domain}
"""

    # Table
    table = """
## Tracked Files

| Filename | Layer1 | Layer2 | Layer3 | Status | Last Modified |
|----------|--------|--------|--------|--------|----------------|
"""

    for m in metas:
        status = "empty" if not m.layer1_exists else "processed"
        table += f"| {m.filename} | {'✓' if m.layer1_exists else ''} | {'✓' if m.layer2_exists else ''} | {'✓' if m.layer3_exists else ''} | {status} | {m.modified[:10]} |\n"

    tree = "\n## Folder Structure\n\n```\n"
    tree += generate_tree_view(folder)
    tree += "\n```"

    return header + related + table + tree


def update_index(domain: str, layer: int, folder: Path, metas: List[FileMeta]) -> bool:
    try:
        index_path = folder / "INDEX.md"
        content = layer_to_index(domain, layer, folder, metas)
        index_path.write_text(content, encoding="utf-8")
        return True
    except Exception:
        raise


# =========================
# DOMAIN PROCESSING
# =========================

def process_domain(domain: str) -> DomainStats:
    stats = DomainStats(domain=domain)

    try:
        raw_files = scan_raw_files(domain)
        stats.scanned_files = len(raw_files)

        md_folder = get_md_folder(domain)
        chapter_folder = get_chapter_folder(domain)
        chunk_folder = get_chunk_folder(domain)

        safe_mkdir(md_folder)
        safe_mkdir(chapter_folder)
        safe_mkdir(chunk_folder)

        metas: List[FileMeta] = []

        for f in raw_files:
            filename = f.stem

            try:
                md_created = ensure_markdown_file(domain, filename)
                chapter_created = ensure_chapter_folder(domain, filename)
                chunk_created = ensure_chunk_folder(domain, filename)

                if md_created:
                    stats.md_created += 1
                if chapter_created:
                    stats.chapter_created += 1
                if chunk_created:
                    stats.chunk_created += 1

                metas.append(collect_metadata(domain, f))

            except Exception as e:
                stats.errors += 1
                log_error(domain, e)

        # Automatic Layer20 -> Layer30 deterministic chunk build
        try:
            run_chunk_builder(
                domain=domain,
                input_path=chapter_folder,
                output_path=chunk_folder,
                topic="general",
                target_tokens=300,
                minimum_tokens=100,
                maximum_tokens=500,
                recursive=True,
                force=False,
                dry_run=False,
                flat_output=False,
                split_tables=False,
                split_code_blocks=False,
                preserve_headings=True,
                write_manifest=True,
                report_path=chunk_folder / "chunk_builder_report.json",
            )
        except Exception as e:
            stats.errors += 1
            log_error(domain, e)

        # INDEX per layer
        try:
            update_index(domain, 10, md_folder, metas)
            update_index(domain, 20, chapter_folder, metas)
            update_index(domain, 30, chunk_folder, metas)
            stats.index_updated = 3
        except Exception as e:
            stats.errors += 1
            log_error(domain, e)

    except Exception as e:
        log_error(domain, e)

    return stats


# =========================
# MAIN
# =========================

def main():
    start = time.time()

    log("Scanning workspace...", 0)

    domains = discover_domains(WORKSPACE_ROOT)

    total_files = 0
    total_md = 0
    total_ch = 0
    total_cu = 0
    total_idx = 0

    all_stats: List[DomainStats] = []

    for domain in domains:
        log(f"\nDomain: {domain}", 0)
        log(f"Scanning {RAW_PREFIX}{domain}", 1)

        stats = process_domain(domain)
        all_stats.append(stats)

        log(f"{stats.scanned_files} files found", 2)
        log(f"{stats.md_created} markdown created", 2)
        log(f"{stats.chapter_created} chapter folders created", 2)
        log(f"{stats.chunk_created} chunk folders created", 2)
        log("INDEX updated", 2)

        total_files += stats.scanned_files
        total_md += stats.md_created
        total_ch += stats.chapter_created
        total_cu += stats.chunk_created
        total_idx += stats.index_updated

    duration = time.time() - start

    print("\n───────────────────────────────")
    print("\nSummary\n")
    print(f"Domains processed: {len(domains)}")
    print(f"Files scanned: {total_files}")
    print(f"Markdown files created: {total_md}")
    print(f"Folders created (chapter): {total_ch}")
    print(f"Folders created (chunk): {total_cu}")
    print(f"INDEX files generated: {total_idx}")
    print(f"Duration: {duration:.2f}s")


if __name__ == "__main__":
    main()