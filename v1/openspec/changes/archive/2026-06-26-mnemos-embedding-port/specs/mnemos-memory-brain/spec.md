## MODIFIED Requirements

### Requirement: Memory index supports fast recall

The Memory brain SHALL maintain a SQLite FTS index for L1 and searchable L2 content. The index SHALL remain the fast exact-match source for both FTS mode and the FTS branch of hybrid mode, while hybrid mode MAY additionally score indexed L1/L2 text with local lexical/semantic ranking. When real embeddings are enabled via the embedding port, the index SHALL also persist a cached vector per L1 record, and the hybrid semantic branch SHALL score candidates using those cached vectors instead of recomputing record vectors per query. The index schema SHALL be versioned so that adding the vector cache does not break existing indexes, and existing indexes SHALL be rebuildable to populate vectors.

#### Scenario: L1 record is written

- **WHEN** a new L1 memory file is created or updated
- **THEN** the indexer SHALL upsert the record into `memory/index.sqlite`
- **AND** `before_chat` search SHALL query the index instead of scanning all files for exact-match recall

#### Scenario: L1 record is written with embeddings enabled

- **WHEN** a new or updated L1 record is indexed
- **AND** `embedding_provider` is not `off`
- **THEN** the indexer SHALL store a cached vector for the record together with its embedding model identity

#### Scenario: Hybrid recall uses indexed records

- **WHEN** hybrid recall runs
- **THEN** the system SHALL use indexed L1/L2 records as the candidate source
- **AND** it SHALL NOT perform an unbounded full directory walk during chat assembly

#### Scenario: Hybrid semantic branch consumes cached vectors

- **WHEN** hybrid recall runs with real embeddings enabled
- **THEN** the semantic branch SHALL embed only the query and score candidates with cached record vectors
- **AND** records lacking a compatible cached vector SHALL be computed on demand or excluded without raising

#### Scenario: Unsafe FTS query characters

- **WHEN** a user query contains punctuation or characters that would make SQLite FTS `MATCH` fail
- **THEN** the Memory search layer SHALL sanitize or safely handle the query
- **AND** chat assembly SHALL continue without throwing an FTS syntax error

#### Scenario: Embeddings disabled preserves current behavior

- **WHEN** `embedding_provider` is `off` or the embedding port is unavailable
- **THEN** hybrid recall SHALL retain its existing hashed lexical/semantic ranking behavior
- **AND** recall results SHALL remain non-empty when relevant L1/L2 memory exists within budget
