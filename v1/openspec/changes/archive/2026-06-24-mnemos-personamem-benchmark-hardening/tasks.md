## 1. Honest Reporting

- [x] 1.1 Extend per-case results with raw model output, prompt character count, context block character count, suite, mode, and strategy metadata.
- [x] 1.2 Report official PersonaMem recall/storage metrics as `null` or `n/a` when no reference keywords are available.
- [x] 1.3 Keep Lite/Mini recall diagnostics working where `recall_keywords` are present.
- [x] 1.4 Update summary printing to distinguish unsupported metrics from zero hit rates.

## 2. Additional Baselines

- [x] 2.1 Add `rag_messages` mode that retrieves top-k relevant raw conversation messages.
- [x] 2.2 Add CLI options for RAG message count and retrieval query sanitization.
- [x] 2.3 Add `--full-context-strategy` with at least `head` and `tail`.
- [x] 2.4 Record full-context strategy and effective context size in reports.

## 3. Tests

- [x] 3.1 Update PersonaMem benchmark smoke tests for new report fields.
- [x] 3.2 Add a test that official-style cases without recall keywords produce unsupported recall metrics.
- [x] 3.3 Add a test that Lite cases still produce storage/retrieval diagnostics.
- [x] 3.4 Run `py -3 meclaw2/tests/test_personamem_benchmark_smoke.py`.

## 4. Documentation

- [x] 4.1 Update `meclaw2/tests/benchmark/personamem/README.md` with recommended commands.
- [x] 4.2 Document how to interpret `memory`, `baseline`, `rag_messages`, and `full_context`.
- [x] 4.3 Add notes that official 50-case runs are noisy and 200+ cases should be used for stronger comparisons.

### Validation notes (2026-06-24)

All 6 smoke tests pass. Confirmed:
- Lite suite: `storage_hit_rate: 100.0%`, `retrieval_hit_rate: 100.0%` (keywords present)
- Official suite: `storage_hit_rate: n/a (no keywords)`, `retrieval_hit_rate: n/a (no keywords)` (correct)
- `rag_messages` mode runs, `avg_recall_count > 0`
- `full_context` with `--full-context-strategy tail` prints `strategy=tail` in summary
