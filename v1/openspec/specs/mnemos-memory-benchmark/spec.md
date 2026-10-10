# mnemos-memory-benchmark Specification

## Purpose
TBD - created by archiving change mnemos-personamem-benchmark-hardening. Update Purpose after archive.
## Requirements
### Requirement: PersonaMem benchmark supports comparable evaluation modes

The benchmark tooling SHALL support PersonaMem-style MCQ evaluation across modes that make memory behavior comparable.

#### Scenario: Run memory mode

- **WHEN** the benchmark runs with `--mode memory`
- **THEN** it SHALL replay conversation turns through MNEMOS memory write hooks
- **AND** it SHALL answer using the Memory brain recall path rather than full raw history

#### Scenario: Run recent-tail baseline

- **WHEN** the benchmark runs with `--mode baseline`
- **THEN** it SHALL answer using only a bounded recent conversation tail
- **AND** it SHALL NOT write memory records for scoring that case

#### Scenario: Run raw-message retrieval baseline

- **WHEN** the benchmark runs with `--mode rag_messages`
- **THEN** it SHALL retrieve top-k relevant raw conversation messages with local deterministic retrieval
- **AND** it SHALL include those messages as the answer context

#### Scenario: Run full-context mode

- **WHEN** the benchmark runs with `--mode full_context`
- **THEN** it SHALL include a bounded raw conversation context according to the selected full-context strategy
- **AND** the report SHALL record the strategy and effective context size

### Requirement: Benchmark reports are diagnostic and honest

Benchmark reports SHALL preserve enough per-case information to explain scores and SHALL NOT report unsupported metrics as successful.

#### Scenario: Official data lacks recall references

- **WHEN** a benchmark case has no recall keywords or reference snippets available
- **THEN** `storage_hit_rate` and `retrieval_hit_rate` SHALL be reported as unavailable for that case
- **AND** aggregate summaries SHALL show `n/a` or `null` for unsupported recall metrics

#### Scenario: Per-case result is written

- **WHEN** a case is scored
- **THEN** the result SHALL include `predicted`, `correct`, `is_correct`, `raw_model_output`, `prompt_chars`, `context_block_chars`, `recall_count`, `suite`, and `mode`
- **AND** the report SHALL be sufficient to inspect parsing failures without repeating the API call

#### Scenario: Dry run mode

- **WHEN** the benchmark runs with `--dry-run`
- **THEN** it SHALL skip LLM scoring
- **AND** it SHALL still report storage, retrieval, and context diagnostics where supported

### Requirement: Benchmark data handling is local and reproducible

Benchmark tooling SHALL keep downloaded official datasets out of tracked source and make runs reproducible from command-line arguments.

#### Scenario: Download official dataset

- **WHEN** the user runs the download helper
- **THEN** official PersonaMem files SHALL be saved under the benchmark data directory
- **AND** downloaded dataset files SHALL remain git-ignored

#### Scenario: Report records configuration

- **WHEN** a benchmark run writes a JSON report
- **THEN** the report SHALL include suite, mode, limit, profile id, extraction mode, and relevant context strategy parameters

