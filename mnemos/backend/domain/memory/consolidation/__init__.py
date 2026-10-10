"""Memory consolidation: merge, compress, archive."""

from .engine import capacity_exceeded, maybe_run_consolidation, run_consolidation

__all__ = ["capacity_exceeded", "maybe_run_consolidation", "run_consolidation"]
