"""Export MeClaw 1.0 runnable snapshot to ../meclaw1.0 with sanitization."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT.parent / "meclaw1.0"

COPY_DIRS = ("backend", "web", "skills", "assets")
COPY_FILES = (
    "main.py",
    "requirements.txt",
    "build.bat",
    "config.example.json",
    "_launch.cmd",
    "启动MeClaw.bat",
    "启动MeClaw(调试).bat",
    "启动MeClaw.vbs",
    "安装依赖.bat",
    "创建桌面快捷方式.bat",
)

DOC_KEEP = ("docs/记忆系统使用帮助.md",)

SKIP_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".cursor",
    ".claude",
    ".vscode",
    ".idea",
    "node_modules",
}

KEY_PATTERNS = (
    re.compile(r"sk-[a-zA-Z0-9]{16,}"),
    re.compile(r"Bearer\s+[a-zA-Z0-9._\-]{20,}"),
)

DEFAULT_SOUL = """# 默认助手

你是 MeClaw 的默认对话助手，回答简洁、准确、友好。

## 行为

- 使用简体中文，除非用户要求其他语言
- 不确定时直接说明，不编造事实
- 尊重用户隐私，不主动索要敏感信息
"""

README = """# MeClaw 1.0

本地桌面 AI 助手（Python + pywebview）。

## 快速开始

1. 复制 `config.example.json` 为 `config.json`，填入你的 API 信息
2. `pip install -r requirements.txt`
3. `python main.py` 或双击 `启动MeClaw.bat`

## 说明

- 本目录为可运行快照，不含开发用内部文档与本地运行时数据
- `config.json`、`history/`、`downloads/` 请自行在本地维护，勿外传
- Bot 人设文件位于 `souls/`，默认使用 `souls/default`
"""


def should_skip_path(path: Path) -> bool:
    for part in path.parts:
        if part in SKIP_DIR_NAMES or part.startswith("."):
            return True
    return False


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        if should_skip_path(rel):
            continue
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def remove_dot_artifacts(base: Path) -> None:
    for path in sorted(base.rglob("*"), reverse=True):
        name = path.name
        if name.startswith(".") or name in SKIP_DIR_NAMES:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink(missing_ok=True)


def sanitize_text(path: Path) -> None:
    if path.suffix.lower() not in {".py", ".js", ".json", ".md", ".html", ".txt", ".bat", ".vbs"}:
        return
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    original = text
    for pattern in KEY_PATTERNS:
        text = pattern.sub("YOUR_API_KEY_HERE", text)
    if text != original:
        path.write_text(text, encoding="utf-8", newline="\n")


def sanitize_tree(base: Path) -> None:
    for path in base.rglob("*"):
        if path.is_file():
            sanitize_text(path)


def write_config(dest: Path) -> None:
    example = dest / "config.example.json"
    target = dest / "config.json"
    if example.exists():
        data = json.loads(example.read_text(encoding="utf-8"))
        for profile in data.get("api_profiles", []):
            profile["api_key"] = ""
            profile["base_url"] = profile.get("base_url") or "https://api.example.com/v1"
        data["web_search_api_key"] = ""
        target.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def main() -> None:
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)

    for name in COPY_DIRS:
        copy_tree(ROOT / name, DEST / name)

    for name in COPY_FILES:
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, DEST / name)

    docs_dir = DEST / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    for rel in DOC_KEEP:
        src = ROOT / rel
        if src.exists():
            shutil.copy2(src, docs_dir / src.name)

    souls_default = DEST / "souls" / "default"
    souls_default.mkdir(parents=True, exist_ok=True)
    (souls_default / "soul.md").write_text(DEFAULT_SOUL, encoding="utf-8", newline="\n")
    (DEST / "souls" / "README.md").write_text(
        "每个 Bot 对应一个子目录，至少包含 `soul.md`。\n",
        encoding="utf-8",
        newline="\n",
    )

    (DEST / "README.md").write_text(README, encoding="utf-8", newline="\n")

    remove_dot_artifacts(DEST)
    sanitize_tree(DEST)
    write_config(DEST)

    print(f"Exported MeClaw 1.0 snapshot to: {DEST}")


if __name__ == "__main__":
    main()
