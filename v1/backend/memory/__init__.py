"""Bot memory: folder storage + SQLite FTS index."""

from .config import get_memory_settings
from .retrieval import search_memory, format_memory_block

__all__ = [
    "get_memory_settings",
    "search_memory",
    "format_memory_block",
]
