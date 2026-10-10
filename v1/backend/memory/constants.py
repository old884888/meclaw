import re

ITEM_TYPES = ("fact", "preference", "project", "relationship", "quote")
ENTRY_TYPES = ("fact", "preference", "project", "relationship", "quote")

MEMORY_MD_CAP = 4096
CHUNK_TARGET = 1200
CHUNK_MIN = 800
CHUNK_MAX = 1500

RECENCY_HALF_LIFE_DAYS = {
    "fact": 60,
    "preference": 60,
    "project": 30,
    "relationship": 60,
    "quote": 9999,
    "chunk": 90,
    "entry": 60,
}

RECENCY_WEIGHT = {
    "fact": 0.20,
    "preference": 0.20,
    "project": 0.35,
    "relationship": 0.20,
    "quote": 0.0,
    "chunk": 0.10,
    "entry": 0.20,
}


def slugify(title):
    s = (title or "untitled").strip().lower()
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", s, flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:80] or "untitled"


def estimate_tokens(text):
    if not text:
        return 0
    return max(1, len(text) // 2)
