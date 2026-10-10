"""Per-bot topic registry with embedding centroids."""

from __future__ import annotations

import hashlib
import logging
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from ...storage.common import now_iso, read_json, write_json_atomic

if TYPE_CHECKING:
    from .embedding.port import EmbeddingPort
    from .paths import BotMemoryPaths

logger = logging.getLogger(__name__)

REGISTRY_SCHEMA_VERSION = 1
REGISTRY_FILENAME = "topic_registry.json"

KNOWN_TOPIC_KEYS = frozenset(
    {
        "drink",
        "food",
        "writing",
        "travel",
        "fitness",
        "work",
        "music",
        "reading",
        "media",
        "reply_style",
        "budget",
        "pets",
        "sleep",
    }
)


def registry_path(paths: BotMemoryPaths) -> Any:
    return paths.root / REGISTRY_FILENAME


def _empty_registry(*, embedding_model: str = "") -> dict[str, Any]:
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "embedding_model": embedding_model,
        "updated_at": now_iso(),
        "topics": {},
    }


def load_topic_registry(paths: BotMemoryPaths) -> dict[str, Any]:
    path = registry_path(paths)
    if not path.exists():
        return _empty_registry()
    raw = read_json(path, _empty_registry())
    topics = raw.get("topics")
    if not isinstance(topics, dict):
        raw["topics"] = {}
    raw.setdefault("schema_version", REGISTRY_SCHEMA_VERSION)
    raw.setdefault("embedding_model", "")
    return raw


def save_topic_registry(paths: BotMemoryPaths, registry: dict[str, Any]) -> None:
    payload = deepcopy(registry)
    payload["schema_version"] = REGISTRY_SCHEMA_VERSION
    payload["updated_at"] = now_iso()
    write_json_atomic(registry_path(paths), payload, backup=False)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def running_average_centroid(
    centroid: list[float] | None,
    count: int,
    vector: list[float],
) -> list[float]:
    if not vector:
        return list(centroid or [])
    if not centroid or count <= 0:
        return list(vector)
    total = count + 1
    return [(c * count + v) / total for c, v in zip(centroid, vector)]


def _derive_topic_label(content: str) -> str:
    text = " ".join((content or "").split()).strip()
    if not text:
        return "Topic"
    return text[:24]


def _new_topic_key(content: str) -> str:
    digest = hashlib.sha1((content or "").encode("utf-8")).hexdigest()[:8]
    return f"topic_{digest}"


def get_topic_label_from_registry(registry: dict[str, Any], topic_key: str) -> str:
    entry = (registry.get("topics") or {}).get(topic_key) or {}
    label = str(entry.get("label") or "").strip()
    return label


def ensure_registry_topic(
    registry: dict[str, Any],
    topic_key: str,
    *,
    label: str = "",
    vector: list[float] | None = None,
    embedding_model: str = "",
) -> None:
    topics = registry.setdefault("topics", {})
    entry = topics.get(topic_key) or {}
    if label:
        entry["label"] = label
    elif not entry.get("label"):
        entry["label"] = topic_key.replace("_", " ")
    if vector:
        entry["centroid"] = list(vector)
    entry["atom_count"] = int(entry.get("atom_count") or 0)
    entry["updated_at"] = now_iso()
    topics[topic_key] = entry
    if embedding_model:
        registry["embedding_model"] = embedding_model


def update_topic_centroid(
    paths: BotMemoryPaths,
    topic_key: str,
    vector: list[float],
    *,
    content: str = "",
    label: str = "",
    embedding_port: EmbeddingPort | None = None,
) -> None:
    if not topic_key or not vector:
        return
    registry = load_topic_registry(paths)
    topics = registry.setdefault("topics", {})
    entry = topics.get(topic_key) or {}
    count = int(entry.get("atom_count") or 0)
    centroid = entry.get("centroid")
    if not isinstance(centroid, list):
        centroid = None
    entry["centroid"] = running_average_centroid(centroid, count, vector)
    entry["atom_count"] = count + 1
    entry["updated_at"] = now_iso()
    if label:
        entry["label"] = label
    elif not entry.get("label"):
        entry["label"] = _derive_topic_label(content) if content else topic_key.replace("_", " ")
    topics[topic_key] = entry
    if embedding_port is not None and embedding_port.available:
        registry["embedding_model"] = embedding_port.model_identity
    save_topic_registry(paths, registry)


def find_best_topic(
    registry: dict[str, Any],
    vector: list[float],
    *,
    threshold: float,
) -> tuple[str, float]:
    best_key = ""
    best_score = 0.0
    for key, entry in (registry.get("topics") or {}).items():
        centroid = entry.get("centroid")
        if not isinstance(centroid, list) or not centroid:
            continue
        score = cosine_similarity(vector, centroid)
        if score > best_score:
            best_score = score
            best_key = key
    if best_key and best_score >= threshold:
        return best_key, best_score
    return "", best_score


def cluster_enabled(cfg: dict[str, Any] | None, embedding_port: EmbeddingPort | None) -> bool:
    cfg = cfg or {}
    if not bool(cfg.get("topic_cluster_enabled", True)):
        return False
    if str(cfg.get("embedding_provider") or "off").strip().lower() == "off":
        return False
    if embedding_port is None or not embedding_port.available:
        return False
    return True


def rebuild_topic_centroids(
    paths: BotMemoryPaths,
    *,
    embedding_port: EmbeddingPort | None = None,
) -> dict[str, Any]:
    """Recompute all topic centroids from L1 atoms (e.g. after embedding model change)."""
    from .store_l1 import list_atoms

    if embedding_port is None or not embedding_port.available:
        registry = _empty_registry()
        save_topic_registry(paths, registry)
        return registry

    atoms = list_atoms(paths)
    groups: dict[str, list[str]] = {}
    for atom in atoms:
        key = str(atom.get("topic_key") or "").strip()
        body = str(atom.get("content") or "").strip()
        if not key or not body:
            continue
        groups.setdefault(key, []).append(body)

    registry = _empty_registry(embedding_model=embedding_port.model_identity)
    for topic_key, bodies in groups.items():
        vectors: list[list[float]] = []
        for body in bodies:
            try:
                vec = embedding_port.embed([body])[0]
            except Exception:  # noqa: BLE001
                continue
            if vec:
                vectors.append(vec)
        if not vectors:
            continue
        dim = len(vectors[0])
        centroid = [0.0] * dim
        for vec in vectors:
            if len(vec) != dim:
                continue
            centroid = [a + b for a, b in zip(centroid, vec)]
        centroid = [v / len(vectors) for v in centroid]
        label = _derive_topic_label(bodies[-1])
        registry["topics"][topic_key] = {
            "label": label,
            "centroid": centroid,
            "atom_count": len(bodies),
            "updated_at": now_iso(),
        }

    save_topic_registry(paths, registry)
    logger.info("Rebuilt %d topic centroids for bot", len(registry.get("topics") or {}))
    return registry
