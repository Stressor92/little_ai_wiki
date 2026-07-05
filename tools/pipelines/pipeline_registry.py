from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from tools.pipelines import pipeline_runner


@dataclass(frozen=True)
class StageDefinition:
    name: str
    version: str
    dependencies: tuple[str, ...]
    runner: Callable
    required_inputs: tuple[str, ...] = field(default_factory=tuple)
    produced_outputs: tuple[str, ...] = field(default_factory=tuple)


def get_stage_registry() -> dict[str, StageDefinition]:
    registry = {
        "discover_sources": StageDefinition(
            name="discover_sources",
            version="1.0",
            dependencies=(),
            runner=pipeline_runner.run_discover_sources,
            required_inputs=("layer00",),
            produced_outputs=("discovery_manifest",),
        ),
        "ingest": StageDefinition(
            name="ingest",
            version="1.0",
            dependencies=("discover_sources",),
            runner=pipeline_runner.run_ingest,
            required_inputs=("layer00",),
            produced_outputs=("layer10",),
        ),
        "chapter_splitter": StageDefinition(
            name="chapter_splitter",
            version="1.0",
            dependencies=("ingest",),
            runner=pipeline_runner.run_chapter_splitter,
            required_inputs=("layer10",),
            produced_outputs=("layer20",),
        ),
        "chunk_builder": StageDefinition(
            name="chunk_builder",
            version="1.0",
            dependencies=("chapter_splitter",),
            runner=pipeline_runner.run_chunk_builder,
            required_inputs=("layer20",),
            produced_outputs=("layer30",),
        ),
        "evidence_index": StageDefinition(
            name="evidence_index",
            version="1.0",
            dependencies=("chunk_builder",),
            runner=pipeline_runner.run_evidence_index,
            required_inputs=("layer30",),
            produced_outputs=("layer40",),
        ),
        "embedding_builder": StageDefinition(
            name="embedding_builder",
            version="1.0",
            dependencies=("evidence_index",),
            runner=pipeline_runner.run_embedding_builder,
            required_inputs=("layer40",),
            produced_outputs=("layer50",),
        ),
        "wiki_builder": StageDefinition(
            name="wiki_builder",
            version="1.0",
            dependencies=("evidence_index",),
            runner=pipeline_runner.run_wiki_builder,
            required_inputs=("layer40",),
            produced_outputs=("layer60",),
        ),
        "analysis_builder": StageDefinition(
            name="analysis_builder",
            version="1.0",
            dependencies=("wiki_builder",),
            runner=pipeline_runner.run_analysis_builder,
            required_inputs=("layer60",),
            produced_outputs=("layer80",),
        ),
    }

    if len(registry) != len(set(registry.keys())):
        raise ValueError("duplicate stage registration detected")

    return registry


def resolve_stage_order(registry: dict[str, StageDefinition]) -> list[str]:
    ordered: list[str] = []
    temporary: set[str] = set()
    permanent: set[str] = set()

    def visit(name: str) -> None:
        if name in permanent:
            return
        if name in temporary:
            raise ValueError(f"cyclic stage dependency detected at {name}")
        temporary.add(name)
        stage = registry[name]
        for dep in stage.dependencies:
            if dep not in registry:
                raise ValueError(f"missing dependency '{dep}' for stage '{name}'")
            visit(dep)
        temporary.remove(name)
        permanent.add(name)
        ordered.append(name)

    for name in sorted(registry.keys()):
        visit(name)

    return ordered
