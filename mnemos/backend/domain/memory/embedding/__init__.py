"""Pluggable embedding port for MNEMOS memory retrieval."""

from .factory import create_embedding_port
from .port import EmbeddingPort, NullEmbedding

__all__ = ["EmbeddingPort", "NullEmbedding", "create_embedding_port"]
