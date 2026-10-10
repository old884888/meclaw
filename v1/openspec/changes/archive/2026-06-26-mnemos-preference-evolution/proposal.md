## Why

PersonaMem-style evaluation shows MeClaw2 is strong on static preference and fact recall (~75–86%) but weak on preference evolution (~22%) and change-reason questions (~60%). Root cause: L1 stores whole user sentences without topic linkage; L3 marks only `[当前]/[曾经]` without ordered timelines; retrieval returns scattered atoms instead of full evolution chains for a topic.

## What Changes

- Extend L1 atom metadata with `topic_key`, `polarity`, `seq`, and optional `reason` (heuristic first, LLM path unchanged).
- Rebuild L3 preference sections as ordered evolution timelines with explicit current value and change reasons.
- Enhance hybrid retrieval to expand a hit on one atom into the full ordered chain for the same `topic_key`.
- Add PersonaMem benchmark validation targeting `track_full_preference_evolution` and `recalling_the_reasons_behind_previous_updates`.
- Run `--extract llm` comparison on 50/200 official subset to isolate extraction vs injection bottlenecks.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `mnemos-memory-brain`: L1 extraction metadata, L3 evolution timelines, and topic-chain recall behavior.

## Impact

- Affected backend:
  - `meclaw2/backend/domain/memory/l1_extractor.py`
  - `meclaw2/backend/domain/memory/store_l1.py`
  - `meclaw2/backend/domain/memory/profile_aggregator.py`
  - `meclaw2/backend/domain/memory/retrieval.py` or hybrid search module
  - `meclaw2/backend/domain/memory/memory_brain.py`
- L1 frontmatter schema version bump; old atoms remain readable (missing fields default safely).
- PersonaMem official benchmark expected to improve on evolution/reason question types.
