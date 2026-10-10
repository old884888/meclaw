## Context

MNEMOS now has a PersonaMem-style benchmark harness under `meclaw2/tests/benchmark/personamem/`. It can run Lite, Mini, and official PersonaMem 32k subsets across `memory`, `baseline`, and `full_context` modes. Early runs exposed several interpretation problems: official recall metrics are not meaningful without reference keywords, `full_context` is a fixed head truncation, and reports do not retain enough per-case diagnostic data for analysis.

This change is test tooling only. It should not alter runtime chat behavior.

## Goals / Non-Goals

**Goals:**

- Make benchmark reports accurate and hard to misread.
- Add stronger baselines for long-memory evaluation.
- Preserve cheap smoke tests for local development.
- Make benchmark output actionable for memory retrieval and extraction work.

**Non-Goals:**

- Improve Memory brain recall itself; that is covered by `mnemos-memory-hybrid-recall`.
- Add a UI for benchmark results.
- Commit official PersonaMem dataset files to the repository.
- Guarantee exact comparability with PersonaMem leaderboard scripts; this is a MNEMOS integration benchmark.

## Decisions

### Decision: Report unsupported recall metrics as null/n/a

For official PersonaMem rows, `recall_keywords` are not available in the current adapter. The benchmark should report `storage_hit_rate` and `retrieval_hit_rate` as unavailable rather than assuming success.

Alternative considered: infer keywords from correct answer/options. Rejected for now because it risks false positives and would hide dataset-adapter quality issues.

### Decision: Persist raw outputs and prompt diagnostics

Each result row should include enough information to debug failures:

- predicted answer
- correct answer
- raw model output
- prompt character count
- context/memory block character count
- recall count
- suite, mode, extraction mode

This enables post-run inspection without re-spending API calls.

### Decision: Add `rag_messages` baseline

The current baseline uses the latest messages, which is intentionally weak for long multi-session memory tasks. Add a local retrieval baseline over raw conversation messages so memory can be compared against "retrieve relevant original messages" rather than only "recent tail".

Alternative considered: remote embedding RAG. Deferred to keep the benchmark local and dependency-free.

### Decision: Make full-context truncation explicit

Add `--full-context-strategy` with `head`, `tail`, and `fit`/default semantics. Reports should record which strategy was used. This prevents treating one arbitrary truncation as the true long-context upper bound.

## Risks / Trade-offs

- [Risk] More report fields make JSON larger. → Mitigation: keep raw prompt text optional; store counts by default.
- [Risk] `rag_messages` local retrieval may be weak. → Mitigation: position it as a stronger baseline than recent-tail, not as a final research-grade RAG.
- [Risk] Benchmark options proliferate. → Mitigation: keep README examples focused on three common commands.

## Migration Plan

1. Update result schema while preserving existing summary fields.
2. Add CLI flags for `rag_messages` and full-context strategy.
3. Update README examples and smoke tests.
4. Existing reports remain readable but may not contain new diagnostic fields.
