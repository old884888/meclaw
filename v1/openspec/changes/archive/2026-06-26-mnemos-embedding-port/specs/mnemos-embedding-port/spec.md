## ADDED Requirements

### Requirement: Pluggable embedding port with selectable source

The system SHALL expose a pluggable embedding port that produces vector embeddings for text, with the source selectable via `embedding_provider` (`local`, `api`, or `off`). The port SHALL present a single contract `embed(texts) -> vectors` regardless of the underlying source.

#### Scenario: Local provider is configured

- **WHEN** `embedding_provider` is `local`
- **THEN** the embedding port SHALL produce vectors using a locally loaded model identified by `embedding_model`
- **AND** the call SHALL NOT require network access

#### Scenario: API provider is configured

- **WHEN** `embedding_provider` is `api`
- **AND** an embedding-capable provider profile and `embedding_model` are configured
- **THEN** the embedding port SHALL produce vectors by calling that provider
- **AND** the returned vectors SHALL share a consistent dimensionality for all texts in a single call

#### Scenario: Embedding is disabled

- **WHEN** `embedding_provider` is `off`
- **THEN** the embedding port SHALL report that real embeddings are unavailable
- **AND** the Memory brain SHALL retain its existing hashed/FTS recall behavior

### Requirement: Embedding failures degrade safely

The embedding port SHALL degrade without blocking chat when the configured source is unavailable, fails to load, or raises at runtime.

#### Scenario: Local dependency or model is missing

- **WHEN** `embedding_provider` is `local`
- **AND** the required dependency or model cannot be loaded
- **THEN** the system SHALL fall back to existing hashed/FTS recall behavior
- **AND** chat assembly SHALL continue without raising

#### Scenario: API embedding call fails

- **WHEN** `embedding_provider` is `api`
- **AND** the embedding request errors or times out
- **THEN** the system SHALL fall back to existing recall behavior for that query
- **AND** the failure SHALL NOT abort the turn

### Requirement: Embeddings are cached at write time

When real embeddings are enabled, the system SHALL compute and persist a vector for each indexed L1 record at write/index time, and SHALL reuse cached vectors for retrieval instead of recomputing record vectors per query.

#### Scenario: L1 record is indexed with embeddings enabled

- **WHEN** a new or updated L1 record is indexed
- **AND** `embedding_provider` is not `off`
- **THEN** the system SHALL store the record's embedding alongside the index entry
- **AND** the stored vector SHALL be associated with the record id and the embedding model identity

#### Scenario: Retrieval reuses cached vectors

- **WHEN** semantic ranking runs with real embeddings enabled
- **THEN** the system SHALL embed only the query text at retrieval time
- **AND** it SHALL score candidates using cached record vectors rather than recomputing them per query

#### Scenario: Cached vector is missing or stale

- **WHEN** a candidate record has no cached vector or its vector was produced by a different embedding model identity
- **THEN** the system SHALL compute the vector on demand or exclude the record from semantic scoring
- **AND** it SHALL NOT raise or block recall

### Requirement: Embedding model identity is tracked for rebuilds

The system SHALL record which embedding model identity produced cached vectors so that index rebuilds can detect and refresh stale vectors.

#### Scenario: Embedding model changes

- **WHEN** `embedding_model` or `embedding_provider` changes such that the model identity differs from cached vectors
- **THEN** a subsequent index rebuild SHALL be able to recompute vectors under the new identity
- **AND** retrieval SHALL not mix scores from incompatible model identities
