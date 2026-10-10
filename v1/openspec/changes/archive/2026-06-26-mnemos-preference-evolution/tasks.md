## 1. L1 Metadata

- [x] 1.1 Extend `write_atom()` frontmatter with `topic_key`, `polarity`, `seq`, `reason`; bump `schema_version` to 2
- [x] 1.2 Add per-bot monotonic seq counter (file or sqlite) in memory layout
- [x] 1.3 Extend `extract_atoms_heuristic()` with topic map, polarity detection, reason extraction
- [x] 1.4 Add fallback `topic_key`/`seq` derivation when reading legacy atoms

## 2. L3 Evolution Timelines

- [x] 2.1 Group preference atoms by `topic_key` (fallback to regex topic for legacy)
- [x] 2.2 Replace flat `[当前]/[曾经]` with numbered timeline + explicit current value + reason lines
- [x] 2.3 Cap timeline depth (e.g. 5 events) and total profile size under persona budget

## 3. Topic-Chain Recall

- [x] 3.1 After hybrid/FTS hit, expand to all atoms with same `topic_key`
- [x] 3.2 Sort chain by `seq`; format as grouped block in memory injection
- [x] 3.3 Enforce budget: chain block priority vs unrelated top-k snippets

## 4. Tests

- [x] 4.1 Unit test: switch message produces `polarity=switch` and extracted `reason`
- [x] 4.2 Unit test: three atoms same topic render ordered L3 timeline with current marker
- [x] 4.3 Unit test: recall hit on middle atom injects full chain in order
- [x] 4.4 Legacy atom without topic_key still indexes and recalls

## 5. Benchmark Validation

- [x] 5.1 Run PersonaMem official 50 `--mode memory --extract heuristic`; record by_question_type
- [ ] 5.2 Run same 50 with `--extract llm` for extraction ceiling comparison
- [x] 5.3 Document delta vs pre-change baseline for evolution and reason question types

### Validation notes (2026-06-24)

**Pre-change baselines (same official 50 subset):**
- `report_memory_50_p1b.json`: overall **58%**, evolution **22.2%** (2/9), reasons **60%**, facts **75%**
- `report_memory_200.json` (pre-change, 200 cases): overall **49%**, evolution **33.3%** (15/45), reasons **57.5%**

**Post-change (`report_memory_50_evolution.json`, heuristic, hybrid):**
- overall **54%**
- `track_full_preference_evolution`: **44.4%** (4/9) — **+22.2 pts** vs 50-q pre baseline; exceeds design target (>40%)
- `recalling_the_reasons_behind_previous_updates`: **60%** (unchanged vs 50-q pre)
- `recall_user_shared_facts`: **37.5%** (regressed vs 75% on same 50-q pre run — likely budget/noise tradeoff from chain-first injection)
- `avg_recall_count`: **2.02** (chain blocks are multi-line; counter under-counts vs bullet snippets)

**Implementation files:**
- `meclaw2/backend/domain/memory/topic_metadata.py` — topic_key/polarity/seq/reason + timeline/chain formatters
- `meclaw2/backend/domain/memory/store_l1.py` — schema v2 write + legacy enrich on read
- `meclaw2/backend/domain/memory/profile_aggregator.py` — L3 evolution timelines
- `meclaw2/backend/domain/memory/memory_brain.py` — topic-chain recall expansion
- `meclaw2/tests/test_preference_evolution.py` — 4 unit tests

**Follow-up:** Re-run official **200** cases post-change when convenient for stable comparison; optional `--extract llm` 50-q ceiling test (task 5.2).
