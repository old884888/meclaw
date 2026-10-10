## 1. Foundation — domain layout and config



- [x] 1.1 Add `meclaw2/backend/domain/brains/` package with `orchestrator.py`, `router.py`, `persona_brain.py`, `cognitive_brain.py`, `learner_brain.py`, `budgets.py`.

- [x] 1.2 Extend `config_store.py` defaults with `multi_brain_enabled`, brain toggles, token budgets, compaction thresholds, and learner schedule fields.

- [x] 1.3 Define per-bot memory path helpers under `souls/{bot_id}/memory/` aligned with design layout (l0/l1/l2/l3, index.sqlite, replacement_cache).



## 2. Phase A — Orchestrator wiring in chat main path



- [x] 2.1 Implement rule-based `router.py` for persona/memory/cognitive/cross-session activation with zero LLM cost.

- [x] 2.2 Implement `persona_brain.py` to produce bounded soul + L3 excerpt blocks.

- [x] 2.3 Implement `orchestrator.prepare_turn()` assembling messages in stable cache-friendly order.

- [x] 2.4 Wire `_save_user_message_and_prepare()` and `_edit_last_user_and_prepare()` in `main.py` to use orchestrator when `multi_brain_enabled` is true.

- [x] 2.5 Schedule async `after_turn` and learner `collect_signal` after generation completes in `_run_generation()`.

- [x] 2.6 Add optional `brain_trace` WebSocket event behind `brain_trace_enabled` config.



## 3. Phase B — Memory brain MVP



- [x] 3.1 Implement `memory_brain.py` as MemoryService facade replacing direct use of knowledge-centric `LayeredMemoryService` for chat recall.

- [x] 3.2 Implement L0 turn evidence writer (`store_l0.py`) and hook from `after_turn`.

- [x] 3.3 Implement L1 atomic memory store (`store_l1.py`) with fact/preference/constraint/todo types and frontmatter schema.

- [x] 3.4 Implement L1 extractor (async LLM) with configurable `l1_extract_every_turn` and max token cap.

- [x] 3.5 Implement L2 session summary read/write under `history/summaries/` and bot memory l2 mirror if needed.

- [x] 3.6 Implement L3 `user_profile.md` read/update pipeline with bounded excerpt for persona brain.

- [x] 3.7 Implement `memory/indexer.py` SQLite FTS for L1/L2 and integrate into `before_chat`.

- [x] 3.8 Implement soft delete + audit log for memory records.



## 4. Phase C — Context compaction engine



- [x] 4.1 Implement `compaction.py` with tier thresholds relative to profile `max_context`.

- [x] 4.2 Implement Tier 1 snip for long tool/text content with offload paths.

- [x] 4.3 Implement Tier 2 prune with per-session `replacement_cache` and monotonic decisions.

- [x] 4.4 Implement Tier 3 incremental running summary with single LLM call and protection zone split.

- [x] 4.5 Integrate compaction into orchestrator so compression completes before `stream_chat` when required.



## 5. Phase D — Cognitive brain and cross-session recall



- [x] 5.1 Implement `cognitive_brain.py` structured block for planning/implementation intents only.

- [x] 5.2 Extend router cross-session patterns and memory brain recall for prior session L2 summaries.

- [x] 5.3 Add L0 deep-recall path for explicit trace/quote intents with strict budget limits.



## 6. Phase E — Learner brain and UI



- [x] 6.1 Implement `learner_brain.py` signal store and scheduled batch entry point.

- [x] 6.2 Implement candidate profile/prompt output files with pending approval status (no auto-apply).

- [x] 6.3 Add settings UI toggles for brain switches and budgets (minimal first pass).

- [x] 6.4 Add memory panel API stubs: list L1/L3, trace to L0, soft delete.

- [x] 6.5 Deprecate or delegate `layered.py` knowledge-recall path so personal chat does not pull `knowledge/notes` by default.



## 7. Tests and verification



- [x] 7.1 Add smoke tests: orchestrator message order, router activation matrix, budget truncation.

- [x] 7.2 Add smoke tests: L0 write after turn, L1 index search, L2 summary update interval.

- [x] 7.3 Add smoke tests: tier1/2 compaction without LLM, tier3 summary path, replacement cache monotonicity.

- [x] 7.4 Add smoke tests: learner collects signals without blocking; candidates do not modify soul.md.

- [ ] 7.5 Manual verify: long session without manual compress, cross-session “继续上次”, cognitive intent only on planning messages, `brain_trace` optional.

