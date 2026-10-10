## Why

PersonaMem primarily evaluates whether an assistant understands user preferences and their evolution, not just whether it can recall isolated facts. MNEMOS has L1/L2 memory primitives, but needs a stable L3 persona/profile layer that summarizes durable preferences and constraints for prompt injection.

## What Changes

- Add L3 profile generation/refresh from L1 atoms and L2 summaries.
- Store the profile as a bot-scoped, human-readable memory artifact separate from `soul.md`.
- Inject a bounded L3 profile excerpt before chat when memory/persona budgets allow.
- Track preference evolution so newer constraints can supersede older preferences without deleting evidence.
- Add tests and PersonaMem-style validation for preference evolution and personalized recommendations.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `mnemos-memory-brain`: Extend L3 profile behavior from a placeholder requirement to concrete generation, storage, update, and injection semantics.

## Impact

- Affected backend areas:
  - `meclaw2/backend/domain/memory/l3_aggregator.py`
  - `meclaw2/backend/domain/memory/memory_brain.py`
  - `meclaw2/backend/domain/brains/persona_brain.py`
  - `meclaw2/backend/domain/brains/brain_status.py`
  - `meclaw2/tests/`
- No automatic edits to `soul.md`.
- No external dependency required for a heuristic first pass; optional LLM profile refresh may use existing configured background model later.
