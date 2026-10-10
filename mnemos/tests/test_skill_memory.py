"""Tests for P6b skill memory storage and recall."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.skills.intent import query_wants_skill_recall
from backend.domain.skills.paths import ensure_skill_layout
from backend.domain.skills.recall import recall_skills_block
from backend.domain.skills.store import create_skill_from_candidate, list_skills, write_skill


class MockEmbedding:
    available = True
    model_identity = "test:mock:4"

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            if "outfit" in (t or "").lower() or "穿搭" in (t or ""):
                out.append([1.0, 0.0, 0.0, 0.0])
            else:
                out.append([0.0, 1.0, 0.0, 0.0])
        return out


def test_query_wants_skill_recall() -> None:
    assert query_wants_skill_recall("请给我写一份操作步骤教程")
    assert not query_wants_skill_recall("今天天气怎么样")


def test_only_approved_skills_injected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls = Path(tmp) / "souls"
        paths = ensure_skill_layout(souls, "b_skill")
        write_skill(
            paths,
            title="Draft skill",
            content="hidden draft",
            status="pending",
        )
        write_skill(
            paths,
            title="Outfit writing guide",
            content="Describe outfit with concrete fabric and shoe details",
            status="approved",
        )
        block = recall_skills_block(
            souls,
            "b_skill",
            "怎么做穿搭描述教程",
            cfg={"skill_recall_enabled": True, "skill_token_budget": 400},
            embedding_port=MockEmbedding(),
        )
        assert block
        assert "Outfit writing guide" in block
        assert "hidden draft" not in block
        assert list_skills(paths, status="approved")


def test_create_skill_from_candidate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls = Path(tmp) / "souls"
        skill = create_skill_from_candidate(
            souls,
            "b_skill",
            title="Email writing",
            content="Step 1: greet\nStep 2: body",
        )
        assert skill["status"] == "approved"
        assert "Step 1" in skill["content"]
