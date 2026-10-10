"""Soul folder persistence."""

from __future__ import annotations

from pathlib import Path


DEFAULT_SOUL = """你是 MNEMOS，一个可靠、克制、专注的中文对话助手。

要求：
1. 优先回答用户问题，信息准确，不胡编。
2. 不清楚时明确说明并给出下一步建议。
3. 输出结构简洁，先结论后细节。
"""

DEFAULT_PLATFORM_CONSTRAINTS = """## Reasoning

When the model emits a separate reasoning / thinking trace:

- Reason in first person as the character. It is internal monologue, not a briefing to a third party and not a "switching into role" narrator.
- No meta narration: do not open with lines like "Okay, I am X now", "I need to speak in Y tone", "As an AI/assistant", "I am role-playing", or "Let me adopt the persona". You already are the character—start thinking in scene.
- Begin from the immediate situation and react in voice. Do not announce identity or performance first.
"""

PLATFORM_DIR_NAME = "_platform"


def bot_soul_dir(souls_root: Path, bot_id: str) -> Path:
    return souls_root / bot_id


def ensure_bot_soul_layout(souls_root: Path, bot_id: str) -> None:
    root = bot_soul_dir(souls_root, bot_id)
    memory_dir = root / "memory"
    root.mkdir(parents=True, exist_ok=True)
    memory_dir.mkdir(parents=True, exist_ok=True)

    soul_path = root / "soul.md"
    if not soul_path.exists():
        soul_path.write_text(DEFAULT_SOUL, encoding="utf-8")

    gitkeep = memory_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")
    from ..domain.memory.paths import ensure_bot_memory_layout

    ensure_bot_memory_layout(souls_root, bot_id)


def read_soul(souls_root: Path, bot_id: str) -> str:
    ensure_bot_soul_layout(souls_root, bot_id)
    return (bot_soul_dir(souls_root, bot_id) / "soul.md").read_text(encoding="utf-8")


def write_soul(souls_root: Path, bot_id: str, content: str) -> None:
    ensure_bot_soul_layout(souls_root, bot_id)
    (bot_soul_dir(souls_root, bot_id) / "soul.md").write_text((content or "").strip() + "\n", encoding="utf-8")


def read_constraints(souls_root: Path, bot_id: str) -> str:
    path = bot_soul_dir(souls_root, bot_id) / "constraints.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_constraints(souls_root: Path, bot_id: str, content: str) -> None:
    ensure_bot_soul_layout(souls_root, bot_id)
    path = bot_soul_dir(souls_root, bot_id) / "constraints.md"
    text = (content or "").strip()
    if text:
        path.write_text(text + "\n", encoding="utf-8")
    elif path.exists():
        path.unlink()


def read_platform_constraints(souls_root: Path) -> str:
    path = souls_root / PLATFORM_DIR_NAME / "constraints.md"
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    return DEFAULT_PLATFORM_CONSTRAINTS.strip()


def build_system_prompt(
    soul: str,
    *,
    bot_constraints: str = "",
    platform_constraints: str = "",
) -> str:
    parts = [(soul or "").strip()]
    bot_text = (bot_constraints or "").strip()
    platform_text = (platform_constraints or "").strip()
    if bot_text:
        parts.append(f"[约束]\n{bot_text}")
    if platform_text:
        parts.append(f"[Platform constraints]\n{platform_text}")
    return "\n\n".join(p for p in parts if p)

