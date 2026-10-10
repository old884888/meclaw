## Why

PersonaMem official 32k benchmark exposed that MNEMOS can persist memory but does not reliably inject useful recall before answering: `memory` scored 48% vs `baseline` 38%, while `avg_recall_count` stayed at 0.0. This means the Memory brain writes L1 evidence, but current FTS-only query matching is too weak for personalized, semantic questions.

## What Changes

- Upgrade Memory brain `before_chat` recall from FTS-only matching to a hybrid recall path suitable for personalization tasks.
- Add query expansion for personal-memory intents so questions like recommendations, style requests, and preference-sensitive decisions can recall relevant L1/L2 memories even without keyword overlap.
- Return a non-empty, budgeted `[相关记忆]` block when relevant memory exists, with traceable snippets and stable ordering.
- Keep memory disabled behavior unchanged: no retrieval when `memory_enabled` or `memory_retrieval_enabled` is false.
- Add smoke/benchmark coverage that verifies memory recall injection is non-zero for PersonaMem-style cases.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `mnemos-memory-brain`: Change `before_chat` recall requirements from FTS-only top-k matching to hybrid, personalization-aware recall with budgeted injection.

## Impact

- Affected backend areas:
  - `meclaw2/backend/domain/memory/memory_brain.py`
  - `meclaw2/backend/domain/memory/indexer.py`
  - `meclaw2/backend/domain/memory/store_l1.py`
  - `meclaw2/tests/benchmark/personamem/`
- No new external service dependency is required for the first implementation; hybrid scoring should use existing local text features first.
- Existing config keys remain valid. `memory_retrieval_strategy` may be used to switch between `fts` and `hybrid`.
