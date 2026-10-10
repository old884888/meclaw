"""Knowledge and layered memory directory layout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class KnowledgePaths:
    root: Path
    raw_dir: Path
    notes_dir: Path
    sources_file: Path
    index_db: Path


@dataclass
class MemoryLayerPaths:
    root: Path
    l0_dir: Path
    l2_dir: Path
    l3_dir: Path


def knowledge_paths(data_root: Path) -> KnowledgePaths:
    root = data_root / "knowledge"
    return KnowledgePaths(
        root=root,
        raw_dir=root / "raw",
        notes_dir=root / "notes",
        sources_file=root / "sources.json",
        index_db=root / "index.sqlite",
    )


def memory_layer_paths(data_root: Path) -> MemoryLayerPaths:
    root = data_root / "memory"
    return MemoryLayerPaths(
        root=root,
        l0_dir=root / "l0",
        l2_dir=root / "l2",
        l3_dir=root / "l3",
    )


def ensure_knowledge_layout(data_root: Path) -> KnowledgePaths:
    paths = knowledge_paths(data_root)
    paths.raw_dir.mkdir(parents=True, exist_ok=True)
    paths.notes_dir.mkdir(parents=True, exist_ok=True)
    if not paths.sources_file.exists():
        paths.sources_file.write_text('{"sources": []}', encoding="utf-8")
    return paths


def ensure_memory_layout(data_root: Path) -> MemoryLayerPaths:
    paths = memory_layer_paths(data_root)
    for d in (paths.l0_dir, paths.l2_dir, paths.l3_dir):
        d.mkdir(parents=True, exist_ok=True)
    wiki_dir = data_root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    return paths
