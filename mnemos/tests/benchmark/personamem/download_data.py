"""Download official PersonaMem 32k benchmark files from HuggingFace."""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
HF_BASE = "https://huggingface.co/datasets/bowen-upenn/PersonaMem/resolve/main"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {dest}")
    try:
        urllib.request.urlretrieve(url, dest)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Download failed ({exc.code}): {url}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Download PersonaMem 32k benchmark files")
    parser.add_argument("--out-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    out = args.out_dir
    files = [
        ("questions_32k.csv", out / "questions_32k.csv"),
        ("shared_contexts_32k.jsonl", out / "shared_contexts_32k.jsonl"),
    ]
    for name, dest in files:
        if dest.exists():
            print(f"Skip existing {dest}")
            continue
        _download(f"{HF_BASE}/{name}", dest)
    print("Done.")


if __name__ == "__main__":
    main()
