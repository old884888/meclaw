"""Float32 vector serialization for SQLite BLOB storage."""

from __future__ import annotations

import struct


def vector_to_blob(vec: list[float]) -> bytes:
    if not vec:
        return b""
    return struct.pack(f"{len(vec)}f", *vec)


def blob_to_vector(blob: bytes | None) -> list[float] | None:
    if not blob:
        return None
    if len(blob) % 4 != 0:
        return None
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))
