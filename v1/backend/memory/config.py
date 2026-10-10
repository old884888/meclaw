"""Resolve memory settings from global config + active bot."""


def get_memory_settings(config, bot):
    """Return normalized memory flags for the active bot."""
    if not config:
        config = {}
    if not bot:
        bot = {}

    def _bool(val, default=True):
        if val is None:
            return default
        return bool(val)

    enabled = _bool(bot.get("memory_enabled", config.get("memory_enabled", True)), True)
    if not enabled:
        return {
            "enabled": False,
            "retrieval": False,
            "write": False,
            "budget": 0,
        }

    retrieval = _bool(
        bot.get("memory_retrieval_enabled", config.get("memory_retrieval_enabled", True)),
        True,
    )
    write = _bool(
        bot.get("memory_write_enabled", config.get("memory_write_enabled", True)),
        True,
    )
    budget = bot.get("memory_token_budget", config.get("memory_token_budget", 1200))
    try:
        budget = int(budget)
    except (TypeError, ValueError):
        budget = 1200

    return {
        "enabled": True,
        "retrieval": retrieval,
        "write": write,
        "budget": max(0, budget),
    }


def get_auto_compress_settings(config, bot):
    """自动压缩：全局 + per-bot 覆盖 memory_auto_extract / memory_extract_threshold_pct。"""
    if not config:
        config = {}
    if not bot:
        bot = {}

    def _resolve_bool(bot_key, global_key, default=False):
        val = bot.get(bot_key)
        if val is None:
            val = config.get(global_key, default)
        return bool(val)

    def _resolve_pct(bot_key, global_key, default=85):
        val = bot.get(bot_key)
        if val is None:
            val = config.get(global_key, default)
        try:
            val = int(val)
        except (TypeError, ValueError):
            val = default
        return max(50, min(98, val))

    return {
        "enabled": _resolve_bool("memory_auto_extract", "memory_auto_extract", False),
        "threshold": _resolve_pct(
            "memory_extract_threshold_pct", "memory_extract_threshold_pct", 85
        ),
    }


def get_compress_summary_detail(config, bot, override=None):
    """摘要详略档位（minimal/standard/detailed/max）。"""
    from .compress_prompts import resolve_compress_summary_detail
    return resolve_compress_summary_detail(config, bot, override)
