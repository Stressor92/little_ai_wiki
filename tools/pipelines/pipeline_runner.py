from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from tools.pipelines.stage_executor import StageResult


def _run_module(module: str, args: list[str]) -> tuple[int, str, str]:
    cmd = [sys.executable, "-m", module, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def _count_md(path: Path) -> int:
    if not path.exists():
        return 0
    return len([p for p in path.rglob("*.md") if p.is_file()])


def run_discover_sources(context) -> StageResult:
    files = [p for p in context.input_path.rglob("*") if p.is_file()]
    return StageResult(status="completed", created=0, updated=0, skipped=0, artifacts=[context.input_path.as_posix()], metadata={"files": len(files)})


def run_ingest(context) -> StageResult:
    out = context.workspace_root / f"10_md_{context.domain}"
    before = _count_md(out)
    code, stdout, stderr = _run_module(
        "tools.ingest.pipeline_ingest",
        ["--domain", context.domain, "--input", str(context.input_path), "--output", str(out), "--recursive"] + (["--dry-run"] if context.dry_run else []) + (["--force"] if context.force else []),
    )
    after = _count_md(out)
    if code != 0:
        return StageResult(status="failed", errors=[stderr.strip() or "ingest failed"])
    created = max(0, after - before)
    status = "created" if created > 0 else "unchanged"
    return StageResult(status=status, created=created, artifacts=[out.as_posix()], warnings=[stdout.strip()] if stdout.strip() else [])


def run_chapter_splitter(context) -> StageResult:
    inp = context.workspace_root / f"10_md_{context.domain}"
    out = context.workspace_root / f"20_chapter_{context.domain}"
    before = _count_md(out)
    args = [str(inp), str(out), "--recursive", "--continue-on-error"]
    if context.force:
        args.append("--overwrite")
    if context.dry_run:
        args.append("--dry-run")
    code, stdout, stderr = _run_module("tools.structure.md_chapter_splitter", args)
    after = _count_md(out)
    if code != 0:
        return StageResult(status="failed", errors=[stderr.strip() or "chapter splitter failed"])
    created = max(0, after - before)
    status = "created" if created > 0 else "unchanged"
    return StageResult(status=status, created=created, artifacts=[out.as_posix()], warnings=[stdout.strip()] if stdout.strip() else [])


def run_chunk_builder(context) -> StageResult:
    inp = context.workspace_root / f"20_chapter_{context.domain}"
    out = context.workspace_root / f"30_chunk_{context.domain}"
    before = _count_md(out)
    args = [
        "--domain", context.domain,
        "--input", str(inp),
        "--output", str(out),
        "--recursive",
    ]
    if context.force:
        args.append("--force")
    if context.dry_run:
        args.append("--dry-run")
    code, stdout, stderr = _run_module("tools.structure.chunk_builder", args)
    after = _count_md(out)
    if code != 0:
        return StageResult(status="failed", errors=[stderr.strip() or "chunk builder failed"])
    created = max(0, after - before)
    status = "created" if created > 0 else "unchanged"
    return StageResult(status=status, created=created, artifacts=[out.as_posix()], warnings=[stdout.strip()] if stdout.strip() else [])


def run_evidence_index(context) -> StageResult:
    inp = context.workspace_root / f"30_chunk_{context.domain}"
    out = context.workspace_root / f"40_index_{context.domain}"
    args = [
        "--domain", context.domain,
        "--input", str(inp),
        "--output", str(out),
    ]
    if context.force:
        args.append("--force")
    if context.dry_run:
        args.append("--dry-run")
    code, stdout, stderr = _run_module("tools.indexing.index_creator", args)
    if code != 0:
        return StageResult(status="failed", errors=[stderr.strip() or "index stage failed"])
    return StageResult(status="completed", artifacts=[out.as_posix()], warnings=[stdout.strip()] if stdout.strip() else [])


def run_embedding_builder(context) -> StageResult:
    inp = context.workspace_root / f"40_index_{context.domain}"
    out = context.workspace_root / f"50_embedding_{context.domain}"
    args = [
        "--domain", context.domain,
        "--input", str(inp),
        "--output", str(out),
    ]
    if context.force:
        args.append("--force")
    if context.dry_run:
        args.append("--dry-run")
    code, stdout, stderr = _run_module("tools.embeddings.embeddings", args)
    if code != 0:
        return StageResult(status="failed", errors=[stderr.strip() or "embedding stage failed"])
    return StageResult(status="completed", artifacts=[out.as_posix()], warnings=[stdout.strip()] if stdout.strip() else [])


def run_wiki_builder(context) -> StageResult:
    module = "tools.wiki.wiki_builder"
    inp = context.workspace_root / f"40_index_{context.domain}"
    out = context.workspace_root / f"60_wiki_{context.domain}"
    args = [
        "--domain", context.domain,
        "--input", str(inp),
        "--output", str(out),
    ]
    if context.force:
        args.append("--force")
    if context.dry_run:
        args.append("--dry-run")
    code, stdout, stderr = _run_module(module, args)
    if code != 0:
        return StageResult(status="failed", errors=[stderr.strip() or "wiki stage failed"])
    return StageResult(status="completed", artifacts=[out.as_posix()], warnings=[stdout.strip()] if stdout.strip() else [])


def run_analysis_builder(context) -> StageResult:
    out = context.workspace_root / f"80_{context.domain}_analysis"
    out.mkdir(parents=True, exist_ok=True)
    marker = out / "INDEX.md"
    if not marker.exists() and not context.dry_run:
        marker.write_text("# Analysis\n", encoding="utf-8")
        return StageResult(status="created", created=1, artifacts=[marker.as_posix()])
    return StageResult(status="unchanged", skipped=1, artifacts=[out.as_posix()])
