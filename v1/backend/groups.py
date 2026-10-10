"""群聊实体：groups/groups.json + groups/{id}/meta.json + memory/"""

import json
import os
from datetime import datetime

from .group_mentions import (
    DEFAULT_CHAIN_BUDGET_MAX,
    DEFAULT_PROACTIVITY_PCT,
    normalize_group_meta,
)


def get_groups_dir(app_dir):
    path = os.path.join(app_dir, "groups")
    os.makedirs(path, exist_ok=True)
    return path


def _index_path(app_dir):
    return os.path.join(get_groups_dir(app_dir), "groups.json")


def _group_dir(app_dir, group_id):
    return os.path.join(get_groups_dir(app_dir), group_id)


def _meta_path(app_dir, group_id):
    return os.path.join(_group_dir(app_dir, group_id), "meta.json")


def _load_index(app_dir):
    path = _index_path(app_dir)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"groups": []}


def _save_index(app_dir, index):
    with open(_index_path(app_dir), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def load_groups(app_dir):
    return _load_index(app_dir).get("groups", [])


def load_group_meta(app_dir, group_id):
    path = _meta_path(app_dir, group_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return normalize_group_meta(meta)


def _default_member_settings(member_bot_ids):
    return {
        bid: {"proactivity_pct": DEFAULT_PROACTIVITY_PCT}
        for bid in (member_bot_ids or [])
    }


def get_group_memory_folder(app_dir, group_id):
    """群记忆根目录（等同 soul_folder，下挂 memory/）。"""
    folder = _group_dir(app_dir, group_id)
    os.makedirs(folder, exist_ok=True)
    return folder


def create_group(app_dir, name, avatar="👥", member_bot_ids=None):
    if not member_bot_ids or len(member_bot_ids) < 2:
        raise ValueError("群聊至少需要 2 个机器人成员")
    group_id = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + os.urandom(4).hex()
    now = datetime.now().isoformat(timespec="seconds")
    meta = normalize_group_meta({
        "id": group_id,
        "name": (name or "新群聊").strip() or "新群聊",
        "avatar": avatar or "👥",
        "member_bot_ids": list(member_bot_ids),
        "max_chain_rounds": DEFAULT_CHAIN_BUDGET_MAX,
        "chain_fast_mode": True,
        "member_settings": _default_member_settings(member_bot_ids),
        "created_at": now,
        "updated_at": now,
    })
    os.makedirs(_group_dir(app_dir, group_id), exist_ok=True)
    with open(_meta_path(app_dir, group_id), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    from .memory.store import ensure_layout
    ensure_layout(get_group_memory_folder(app_dir, group_id))

    index = _load_index(app_dir)
    index_entry = {
        "id": group_id,
        "name": meta["name"],
        "avatar": meta["avatar"],
        "member_bot_ids": meta["member_bot_ids"],
        "member_count": len(member_bot_ids),
        "created_at": now,
        "updated_at": now,
    }
    index["groups"].insert(0, index_entry)
    _save_index(app_dir, index)
    return index_entry


def update_group(
    app_dir,
    group_id,
    name=None,
    avatar=None,
    member_bot_ids=None,
    max_chain_rounds=None,
    member_settings=None,
    chain_fast_mode=None,
    chain_history_limit=None,
    auto_compress_enabled=None,
    auto_compress_threshold=None,
):
    meta = load_group_meta(app_dir, group_id)
    if not meta:
        return None
    if name is not None:
        meta["name"] = (name or meta["name"]).strip() or meta["name"]
    if avatar is not None:
        meta["avatar"] = avatar or meta["avatar"]
    if member_bot_ids is not None:
        if len(member_bot_ids) < 2:
            raise ValueError("群聊至少需要 2 个机器人成员")
        meta["member_bot_ids"] = list(member_bot_ids)
        settings = meta.get("member_settings") or {}
        for bid in meta["member_bot_ids"]:
            settings.setdefault(bid, {"proactivity_pct": DEFAULT_PROACTIVITY_PCT})
        meta["member_settings"] = settings
    if max_chain_rounds is not None:
        meta["max_chain_rounds"] = max(0, min(20, int(max_chain_rounds)))
    if chain_fast_mode is not None:
        meta["chain_fast_mode"] = bool(chain_fast_mode)
    if chain_history_limit is not None:
        meta["chain_history_limit"] = max(0, min(200, int(chain_history_limit)))
    if auto_compress_enabled is not None:
        meta["auto_compress_enabled"] = bool(auto_compress_enabled)
    if auto_compress_threshold is not None:
        meta["auto_compress_threshold"] = max(50, min(98, int(auto_compress_threshold)))
    if member_settings is not None:
        merged = meta.get("member_settings") or {}
        for bid, vals in (member_settings or {}).items():
            if bid not in (meta.get("member_bot_ids") or []):
                continue
            entry = merged.setdefault(bid, {})
            if "proactivity_pct" in vals:
                entry["proactivity_pct"] = max(0, min(100, int(vals["proactivity_pct"])))
            elif "auto_mention_pct" in vals:
                entry["proactivity_pct"] = max(0, min(100, int(vals["auto_mention_pct"])))
        meta["member_settings"] = merged
    meta = normalize_group_meta(meta)
    meta["updated_at"] = datetime.now().isoformat(timespec="seconds")
    with open(_meta_path(app_dir, group_id), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    index = _load_index(app_dir)
    for g in index["groups"]:
        if g["id"] == group_id:
            g["name"] = meta["name"]
            g["avatar"] = meta["avatar"]
            g["member_bot_ids"] = meta["member_bot_ids"]
            g["member_count"] = len(meta["member_bot_ids"])
            g["updated_at"] = meta["updated_at"]
            break
    _save_index(app_dir, index)
    return meta


def delete_group(app_dir, group_id):
    import shutil
    index = _load_index(app_dir)
    index["groups"] = [g for g in index["groups"] if g["id"] != group_id]
    _save_index(app_dir, index)
    folder = _group_dir(app_dir, group_id)
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)


def touch_group(app_dir, group_id):
    """更新群索引 updated_at（有新会话活动时）。"""
    index = _load_index(app_dir)
    now = datetime.now().isoformat(timespec="seconds")
    for g in index["groups"]:
        if g["id"] == group_id:
            g["updated_at"] = now
            break
    _save_index(app_dir, index)
