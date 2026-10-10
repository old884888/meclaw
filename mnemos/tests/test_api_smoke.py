"""API smoke tests (no LLM required). Run with server on 127.0.0.1:8766."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("MNEMOS_BASE_URL", "http://127.0.0.1:8766").rstrip("/")


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=5) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    health = get("/health")
    assert health.get("ok") is True, health

    boot = get("/api/bootstrap")
    assert boot.get("ok") is True, boot
    assert "config" in boot and "bots" in boot

    data_info = get("/api/system/data-info")
    assert data_info.get("ok") is True, data_info
    assert "data_dir" in data_info

    bots = get("/api/bots")
    assert bots.get("ok") is True, bots

    if boot.get("bots"):
        bot_id = boot["bots"][0]["id"]
        brain = get(f"/api/bots/{bot_id}/brain/status")
        assert brain.get("ok") is True, brain
        assert "status" in brain and "health" in brain["status"]

        l0 = get(f"/api/bots/{bot_id}/memory/l0?limit=5")
        assert l0.get("ok") is True, l0
        assert "items" in l0 and "total" in l0

        l1 = get(f"/api/bots/{bot_id}/memory/l1?limit=10")
        assert l1.get("ok") is True, l1
        assert "items" in l1 and "total" in l1

        l2 = get(f"/api/bots/{bot_id}/memory/l2?limit=5")
        assert l2.get("ok") is True, l2
        assert "items" in l2

        l3 = get(f"/api/bots/{bot_id}/memory/l3")
        assert l3.get("ok") is True, l3
        assert "profile" in l3

    print("API smoke test OK")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        print(f"Server not running at {BASE}: {exc}", file=sys.stderr)
        sys.exit(2)
