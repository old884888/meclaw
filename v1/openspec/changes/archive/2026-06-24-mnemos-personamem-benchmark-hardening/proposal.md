## Why

PersonaMem testing is now useful enough to guide MNEMOS memory work, but the current benchmark reports can be misleading: official data shows `storage_hit_rate` and `retrieval_hit_rate` as 100% even when no reference keywords exist, and `full_context` is a head-truncated context rather than a reliable upper bound. Hardening the benchmark will make future memory changes measurable and prevent false conclusions.

## What Changes

- Add a first-class MNEMOS memory benchmark capability covering PersonaMem-style evaluation.
- Make official PersonaMem reports honest: mark unsupported recall metrics as `n/a` instead of 100%.
- Persist per-case diagnostics: predicted answer, correct answer, raw model output, prompt size, memory block size/count, and mode.
- Add stronger comparison modes:
  - `rag_messages`: retrieve top-k raw conversation messages as a baseline.
  - configurable `full_context` strategies such as `head`, `tail`, and `fit`.
- Keep Lite/Mini suites available for fast smoke tests.
- Document interpretation guidelines for memory vs baseline vs full-context results.

## Capabilities

### New Capabilities

- `mnemos-memory-benchmark`: PersonaMem-style benchmark tooling and reporting for MNEMOS memory evaluation.

### Modified Capabilities

- None.

## Impact

- Affected files:
  - `meclaw2/tests/benchmark/personamem/eval_mcq.py`
  - `meclaw2/tests/benchmark/personamem/report.py`
  - `meclaw2/tests/benchmark/personamem/README.md`
  - `meclaw2/tests/test_personamem_benchmark_smoke.py`
- No runtime product behavior changes.
- No new network dependency beyond the existing optional PersonaMem dataset download.
