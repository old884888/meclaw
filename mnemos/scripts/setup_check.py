"""MNEMOS first-run environment check, dependency install, and embedding model prefetch."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

MNEMOS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MNEMOS_ROOT
CONFIG_PATH = MNEMOS_ROOT / "data" / "config.json"
REQ_CORE = MNEMOS_ROOT / "requirements.txt"
REQ_EMB = MNEMOS_ROOT / "requirements-embedding.txt"
DEFAULT_EMB_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MIN_PYTHON = (3, 10)
DEFAULT_CN_PIP_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"


def _pip_index_url() -> str | None:
    for key in ("MNEMOS_PIP_INDEX", "PIP_INDEX_URL"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return raw
    if os.environ.get("MNEMOS_USE_CN_MIRROR", "").strip().lower() in ("1", "true", "yes", "on"):
        return DEFAULT_CN_PIP_INDEX
    return None


def _offline_wheels_dir() -> Path | None:
    for key in ("MNEMOS_OFFLINE_WHEELS", "OFFLINE_WHEELS"):
        raw = os.environ.get(key, "").strip()
        if raw:
            path = Path(raw).resolve()
            if path.is_dir():
                return path
    bundled = (MNEMOS_ROOT / "offline" / "wheels").resolve()
    if bundled.is_dir() and any(bundled.glob("*.whl")):
        return bundled
    return None


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _embedding_provider(cfg: dict) -> str:
    return str(cfg.get("embedding_provider") or "off").strip().lower()


def _embedding_model(cfg: dict) -> str:
    model = str(cfg.get("embedding_model") or "").strip()
    return model or DEFAULT_EMB_MODEL


def _cache_dir() -> Path:
    for key in ("FASTEMBED_CACHE_PATH", "FASTEMBED_CACHE_DIR"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return Path(raw).resolve()
    return (MNEMOS_ROOT / ".fastembed_cache").resolve()


def _cache_has_model(model: str) -> bool:
    cache = _cache_dir()
    if not cache.exists():
        return False
    needle = model.replace("/", "--").lower()
    for path in cache.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if (needle in name) or ("minilm" in name and path.suffix.lower() == ".onnx"):
            if path.stat().st_size > 10_000_000:
                return True
    total = sum(f.stat().st_size for f in cache.rglob("*") if f.is_file())
    return total > 100_000_000


def check_core_deps() -> bool:
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        return False
    return True


def check_embedding_deps() -> bool:
    try:
        import fastembed  # noqa: F401
    except ImportError:
        return False
    return True


def pip_install(req: Path) -> None:
    wheels = _offline_wheels_dir()
    index = _pip_index_url()
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(req)]
    if wheels:
        print(f"\n>>> pip install (离线 wheels: {wheels}) -r {req.name}")
        cmd.extend(["--no-index", f"--find-links={wheels}"])
    else:
        print(f"\n>>> pip install -r {req.name}")
        if index:
            print(f"    使用镜像: {index}")
            cmd.extend(["-i", index])
    subprocess.check_call(cmd, cwd=str(REPO_ROOT))


def download_embedding_model(model: str) -> None:
    print(f"\n>>> 正在下载语义模型（约 470MB，需联网）: {model}")
    print(f"    保存目录: {_cache_dir()}")
    from fastembed import TextEmbedding

    embedder = TextEmbedding(model_name=model, cache_dir=str(_cache_dir()))
    probe = list(embedder.embed(["MNEMOS setup probe"]))
    if not probe or len(probe[0]) < 1:
        raise RuntimeError("模型下载或加载失败")
    print(f"    完成，向量维度: {len(probe[0])}")


def collect_status() -> dict:
    cfg = _load_config()
    provider = _embedding_provider(cfg)
    model = _embedding_model(cfg)
    py_ok = sys.version_info >= MIN_PYTHON
    core_ok = check_core_deps() if py_ok else False
    emb_deps_ok = check_embedding_deps() if py_ok else False
    wants_local = provider == "local"
    model_ok = (not wants_local) or (_cache_has_model(model) if emb_deps_ok else False)
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "python_ok": py_ok,
        "core_ok": core_ok,
        "embedding_provider": provider,
        "wants_local_embedding": wants_local,
        "embedding_model": model if wants_local else "",
        "embedding_deps_ok": emb_deps_ok,
        "embedding_model_ok": model_ok,
        "cache_dir": str(_cache_dir()),
        "data_dir": str((MNEMOS_ROOT / "data").resolve()),
        "ready_to_start": py_ok and core_ok,
        "embedding_ready": (not wants_local) or (emb_deps_ok and model_ok),
        "ready": py_ok and core_ok and ((not wants_local) or (emb_deps_ok and model_ok)),
    }


def print_brief(status: dict | None = None) -> None:
    s = status or collect_status()
    parts = [f"Python {s['python']}" + (" OK" if s["python_ok"] else " 需 3.10+")]
    parts.append("依赖 OK" if s["core_ok"] else "依赖未装")
    if s["wants_local_embedding"]:
        if s["embedding_deps_ok"] and s["embedding_model_ok"]:
            parts.append("语义模型 OK")
        elif not s["embedding_deps_ok"]:
            parts.append("fastembed 未装")
        else:
            parts.append("语义模型未下载 (~470MB)")
    elif s["embedding_provider"] == "api":
        parts.append("语义=API")
    else:
        parts.append("语义=关")
    if not s["ready_to_start"]:
        mark = "请先选 [6] 安装依赖"
    elif not s["embedding_ready"]:
        mark = "可启动 (语义检索未就绪)"
    else:
        mark = "可启动"
    print(f"  环境: {' | '.join(parts)}  →  {mark}")


def print_status(status: dict | None = None) -> None:
    s = status or collect_status()
    print()
    print("  环境检测")
    print("  ----------------------------------------")
    py_mark = "OK" if s["python_ok"] else "需 Python 3.10+"
    print(f"  Python {s['python']}  [{py_mark}]")
    print(f"  核心依赖 (fastapi/uvicorn)  [{'OK' if s['core_ok'] else '未安装'}]")
    prov = s["embedding_provider"]
    if prov == "local":
        print(f"  本地语义模型配置  [local]")
        print(f"    模型: {s['embedding_model']}")
        print(f"    fastembed  [{'OK' if s['embedding_deps_ok'] else '未安装'}]")
        print(f"    模型文件    [{'已缓存' if s['embedding_model_ok'] else '未下载 (~470MB)'}]")
        print(f"    缓存目录: {s['cache_dir']}")
    elif prov == "api":
        print("  语义模型配置  [api — 走云端，无需本地下载]")
    else:
        print("  语义模型配置  [off — 未启用本地语义检索]")
    print(f"  数据目录: {s['data_dir']}")
    print("  ----------------------------------------")
    if s["ready"]:
        print("  结论: 环境完全就绪，可以启动 MNEMOS")
    elif s["ready_to_start"]:
        print("  结论: 可以启动；本地语义模型未就绪时记忆检索会降级")
        print("        可在菜单选 [6] 下载语义模型")
    else:
        print("  结论: 请先运行 [6] 首次安装向导")
    print()


def run_wizard(*, auto_yes: bool = False, skip_embedding_download: bool = False) -> int:
    print()
    print("========================================")
    print("  MNEMOS 首次安装向导")
    print("========================================")
    print()
    print("  本向导会帮你：")
    print("    1. 检查 Python 版本")
    print("    2. 安装运行所需依赖 (requirements.txt)")
    print("    3. 若 config 启用了本地语义模型，安装 fastembed 并下载约 470MB 模型")
    print()
    print(f"  数据与聊天记录目录: {MNEMOS_ROOT / 'data'}")
    print(f"  语义模型缓存目录:   {_cache_dir()}")
    wheels = _offline_wheels_dir()
    if wheels:
        print(f"  离线 wheels 目录:   {wheels}")
    index = _pip_index_url()
    if index:
        print(f"  pip 镜像:           {index}")
    print()

    if sys.version_info < MIN_PYTHON:
        print(f"  [错误] 需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} 或更高版本。")
        print("  请从 https://www.python.org/downloads/ 安装 Python 3.12")
        print("  安装时勾选「Add python.exe to PATH」。")
        return 1

    if not auto_yes:
        ans = input("  按 Enter 开始安装，或输入 n 取消: ").strip().lower()
        if ans in ("n", "no", "q"):
            print("  已取消。")
            return 0

    if not check_core_deps():
        print("\n[1/3] 安装核心依赖 …")
        pip_install(REQ_CORE)
    else:
        print("\n[1/3] 核心依赖已就绪，跳过。")

    cfg = _load_config()
    provider = _embedding_provider(cfg)
    if provider != "local":
        print(f"\n[2/3] config 中 embedding_provider={provider!r}，跳过本地语义模型。")
        print("       可在启动后于「设置 → AI 超级大脑」改为 local 再重新运行本向导。")
        print_status()
        return 0

    model = _embedding_model(cfg)
    if not check_embedding_deps():
        print("\n[2/3] 安装语义检索依赖 (fastembed) …")
        pip_install(REQ_EMB)
    else:
        print("\n[2/3] fastembed 已就绪，跳过。")

    if _cache_has_model(model):
        print(f"\n[3/3] 语义模型已存在于缓存，跳过下载: {model}")
    elif skip_embedding_download:
        print(f"\n[3/3] 已跳过模型下载（离线模式）。请确保 {_cache_dir()} 已从本机拷贝。")
    else:
        print("\n[3/3] 下载本地语义模型 …")
        print("      首次约 470MB，需联网，请耐心等待。")
        if not auto_yes:
            ans = input("      现在下载? [Y/n]: ").strip().lower()
            if ans in ("n", "no"):
                print("      已跳过。启动后首次记忆检索时会自动下载。")
                print_status()
                return 0
        try:
            download_embedding_model(model)
        except Exception as exc:  # noqa: BLE001
            print(f"\n  [警告] 模型下载失败: {exc}")
            print("  你仍可启动 MNEMOS；记忆检索会降级为关键词模式，或稍后再试下载。")
            print_status()
            return 2

    print()
    print("  安装完成！返回菜单选择 [1] 启动服务。")
    print("  首次使用请在浏览器中：设置 → 供应商 → 填写 API Key → 绑定 Bot。")
    print_status()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MNEMOS setup helper")
    parser.add_argument("--status", action="store_true", help="Print detailed environment status")
    parser.add_argument("--brief", action="store_true", help="Print one-line environment summary")
    parser.add_argument("--check-core", action="store_true", help="Exit 0 when Python + core deps OK")
    parser.add_argument(
        "--needs-embedding-setup",
        action="store_true",
        help="Exit 2 when local embedding is configured but deps/model missing",
    )
    parser.add_argument("--wizard", action="store_true", help="Interactive first-run wizard")
    parser.add_argument("--yes", action="store_true", help="Non-interactive wizard (auto confirm)")
    parser.add_argument("--download-embedding", action="store_true", help="Download embedding model only")
    parser.add_argument(
        "--skip-embedding-download",
        action="store_true",
        help="Wizard: skip embedding model download (use copied .fastembed_cache)",
    )
    args = parser.parse_args()

    if args.check_core:
        s = collect_status()
        return 0 if s["ready_to_start"] else 2

    if args.needs_embedding_setup:
        s = collect_status()
        return 2 if s["ready_to_start"] and not s["embedding_ready"] else 0

    if args.brief:
        print_brief()
        return 0 if collect_status()["ready_to_start"] else 2

    if args.status:
        print_status()
        return 0 if collect_status()["ready_to_start"] else 2

    if args.download_embedding:
        cfg = _load_config()
        if _embedding_provider(cfg) != "local":
            print("config 未启用 embedding_provider=local，无需下载。")
            return 0
        if not check_embedding_deps():
            print("请先安装: pip install -r requirements-embedding.txt")
            return 1
        try:
            download_embedding_model(_embedding_model(cfg))
        except Exception as exc:  # noqa: BLE001
            print(f"下载失败: {exc}")
            return 1
        return 0

    if args.wizard:
        return run_wizard(auto_yes=args.yes, skip_embedding_download=args.skip_embedding_download)

    print_status()
    return 0 if collect_status()["ready_to_start"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
