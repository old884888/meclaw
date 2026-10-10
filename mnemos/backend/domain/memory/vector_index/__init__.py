"""Vector index for semantic recall (ANN or linear fallback)."""

from .factory import create_vector_index
from .port import NullVectorIndex, VectorIndex

__all__ = ["VectorIndex", "NullVectorIndex", "create_vector_index"]
