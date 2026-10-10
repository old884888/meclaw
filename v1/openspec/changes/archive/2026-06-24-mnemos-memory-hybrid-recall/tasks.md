## 1. Memory Retrieval Core



- [x] 1.1 Add a local hybrid memory search helper that scores indexed L1/L2 memory with FTS plus lightweight lexical/semantic similarity.

- [x] 1.2 Add deterministic query expansion for personalization-sensitive questions without calling an LLM.

- [x] 1.3 Sanitize FTS `MATCH` queries so punctuation and special characters cannot break chat assembly.

- [x] 1.4 Preserve existing FTS-only behavior when `memory_retrieval_strategy` is `fts`.



## 2. before_chat Integration



- [x] 2.1 Update `MemoryBrain.before_chat()` to choose `fts` or `hybrid` based on effective memory config.

- [x] 2.2 Ensure hybrid recall returns a non-empty `[相关记忆]` block when relevant L1/L2 records exist within budget.

- [x] 2.3 Keep recall ordering deterministic and include layer/type/source hints in snippets.

- [x] 2.4 Enforce `memory_token_budget` by truncating lower-ranked items first.



## 3. Tests and Benchmarks



- [x] 3.1 Add unit/smoke tests for punctuation-safe FTS queries.

- [x] 3.2 Add a PersonaMem-lite style test where stored preference and query have weak keyword overlap but hybrid recall injects memory.

- [x] 3.3 Re-run `py -3 meclaw2/tests/test_multi_brain_smoke.py`.

- [x] 3.4 Re-run PersonaMem official 50-case benchmark in `memory` mode and verify `avg_recall_count` is no longer zero.



## 4. Documentation and Validation



- [x] 4.1 Update benchmark README or notes to explain FTS vs hybrid memory recall.

- [x] 4.2 Document rollback path: set `memory_retrieval_strategy` to `fts` or disable `memory_retrieval_enabled`.

- [x] 4.3 Record before/after PersonaMem 50-case numbers in the change notes or task completion comments.



### Validation notes (2026-06-24)



PersonaMem official 50-case `memory` mode, profile `p_6a4a78d4`, heuristic L1:



| Metric | Before (FTS-only) | After (hybrid) |

|--------|-------------------|----------------|

| accuracy | ~48% | **58%** |

| avg_recall_count | 0 | **11.0** |



Also fixed PersonaMem `shared_contexts_32k.jsonl` loader (`load_shared_contexts`) so official conversations replay into L1 during benchmark.
