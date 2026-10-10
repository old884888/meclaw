# mnemos-vector-recall Specification

## Purpose
TBD - created by archiving change mnemos-vector-recall-rerank. Update Purpose after archive.
## Requirements
### Requirement: ANN vector recall over cached embeddings

The system SHALL provide approximate-nearest-neighbor (ANN) recall over cached L1 record embeddings, replacing the bounded linear scan for the semantic branch when real embeddings and the ANN index are available.

#### Scenario: ANN index is available

- **WHEN** semantic recall runs
- **AND** real embeddings and an ANN index are available
- **THEN** the system SHALL retrieve nearest candidates via the ANN index
- **AND** it SHALL NOT cap candidates at a fixed small linear-scan limit

#### Scenario: Large memory store

- **WHEN** the number of indexed L1 records exceeds the previous linear-scan limit
- **THEN** ANN recall SHALL still consider records beyond that limit
- **AND** older records SHALL remain retrievable rather than being silently excluded

#### Scenario: ANN index unavailable

- **WHEN** the ANN index or its dependency is unavailable
- **THEN** the system SHALL fall back to linear scoring over cached vectors (P1 behavior)
- **AND** recall SHALL continue without raising

### Requirement: ANN index stays consistent with L1 records

The ANN index SHALL be updatable as L1 records are written and rebuildable on demand, consistent with the embedding model identity.

#### Scenario: L1 record is written

- **WHEN** a new or updated L1 record is indexed with embeddings enabled
- **THEN** its vector SHALL be added to or updated in the ANN index

#### Scenario: Index rebuild

- **WHEN** an index rebuild is requested or the embedding model identity changes
- **THEN** the ANN index SHALL be rebuildable from cached vectors under the current identity

### Requirement: Recall produces a unified candidate pool

The system SHALL combine FTS candidates and vector candidates into a single deduplicated candidate pool for downstream reranking.

#### Scenario: Both branches return candidates

- **WHEN** FTS and vector recall both return results
- **THEN** the system SHALL union and deduplicate them by record id into one candidate pool
- **AND** the pool size SHALL be bounded by the configured candidate pool limit

