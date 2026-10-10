## Context

MNEMOS currently persists personal memory through `MemoryBrain.after_turn()` and indexes L1/L2 records in SQLite FTS. PersonaMem testing showed a gap between storage and use: L1 records are created, but `before_chat()` often returns an empty memory block for semantic personalization questions, leaving the model to answer from options or recent context instead of recalled user memory.

The first implementation should stay local-first and dependency-light. The project already has a lightweight hybrid retrieval pattern for Knowledge (`meclaw2/backend/domain/knowledge/hybrid.py`) that can be adapted for memory without introducing remote embeddings.

## Goals / Non-Goals

**Goals:**

- Make Memory brain recall useful for personalized questions where the query and stored preference do not share exact words.
- Keep recall budgeted, deterministic, and traceable to L1/L2 memory records.
- Support `memory_retrieval_strategy = "fts" | "hybrid"` with `hybrid` as the practical default.
- Improve PersonaMem-style benchmark diagnostics so `avg_recall_count` reflects real memory injection.

**Non-Goals:**

- Add remote embedding services in this change.
- Implement full L3 persona generation; that should be a follow-up change.
- Replace the existing FTS index. FTS remains available as a fast and explainable baseline.
- Change Soul files or automatically merge learned memory into `soul.md`.

## Decisions

### Decision: Add local hybrid memory search

Implement a memory hybrid search function that combines:

- FTS ranking from `memory/index.sqlite`
- lightweight lexical/semantic similarity over L1/L2 text
- Reciprocal Rank Fusion (RRF) or equivalent stable merge

This mirrors the existing Knowledge hybrid strategy and avoids new dependencies while improving recall for query/preference mismatch.

Alternative considered: remote embeddings. Deferred because it adds configuration, API cost, and failure modes before the local baseline is fixed.

### Decision: Expand personalization queries before search

Before searching memory, classify broad query intent with deterministic hints and add query terms such as preference, allergy, constraint, style, todo, recommendation, travel, food, and writing. The expanded query is only used for retrieval; it is not shown to the model.

Alternative considered: ask the LLM to rewrite every query. Deferred because recall should not add latency or cost on every turn.

### Decision: Keep memory injection bounded and auditable

`before_chat()` should return a `[相关记忆]` block containing top memory snippets with type/layer labels and source hints where available. Items must be truncated under `memory_token_budget` and sorted deterministically by score.

Alternative considered: inject all L1 records for a bot. Rejected because it hurts prompt cache, cost, and privacy.

### Decision: Make benchmark recall metrics honest

PersonaMem official data lacks `recall_keywords`, so official recall hit rates should be shown as unavailable unless the benchmark can derive references from dataset metadata. Memory success should primarily be judged by accuracy, memory block size/count, and sampled prompt/report inspection.

## Risks / Trade-offs

- [Risk] Local hybrid scoring may return loosely related memories. → Mitigation: keep token budget small, preserve ranking details in trace/report, and add regression tests for irrelevant recall.
- [Risk] Query expansion may over-recall common preferences. → Mitigation: use intent-specific terms and cap each source's contribution.
- [Risk] Benchmark gains may be noisy on 50 samples. → Mitigation: keep 50 as quick smoke, but use 200+ for regression decisions.
- [Risk] More recall text can reduce prompt-cache efficiency. → Mitigation: memory remains in the dynamic tail and under `memory_token_budget`.

## Migration Plan

1. Add hybrid memory search helper alongside the existing FTS search.
2. Wire `MemoryBrain.before_chat()` to respect `memory_retrieval_strategy`.
3. Keep existing FTS behavior when strategy is `fts`.
4. Update tests and PersonaMem benchmark scripts.
5. Rollback by setting `memory_retrieval_strategy` to `fts` or disabling `memory_retrieval_enabled`.

## Open Questions

- Should user-facing settings expose a distinct "memory hybrid recall" label, or reuse the existing retrieval strategy field?
- Should L1 atom files gain explicit `keywords`/`topic` fields in this change, or should that be reserved for the L1 extraction improvement change?
