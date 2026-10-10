## MODIFIED Requirements

### Requirement: before_chat recall is budgeted and layered

The Memory brain `before_chat` hook SHALL return only budgeted, high-priority memory for the current query. Recall SHALL use the configured retrieval strategy: `fts` for exact SQLite FTS matching, or `hybrid` for local FTS plus lightweight semantic/lexical ranking suitable for personalized questions. When relevant L1 or L2 memory exists within budget, `before_chat` SHALL return a non-empty memory block with traceable snippets instead of silently falling back to no recall.

#### Scenario: Default recall on a new message

- **WHEN** `memory_retrieval_enabled` is true
- **THEN** recall SHALL prioritize current session L2 summary, then L1 top-k matches, then optional cross-session L2 when routed
- **AND** recall SHALL NOT inject entire L0 archives by default

#### Scenario: Hybrid recall handles semantic personalization

- **WHEN** `memory_retrieval_strategy` is `hybrid`
- **AND** a user asks a personalization-sensitive question that does not share exact keywords with stored L1 preferences
- **THEN** the Memory brain SHALL use local hybrid ranking and query expansion to retrieve relevant L1 or L2 memories
- **AND** the returned memory block SHALL include at least one relevant snippet when such memory exists within `memory_token_budget`

#### Scenario: FTS strategy remains available

- **WHEN** `memory_retrieval_strategy` is `fts`
- **THEN** the Memory brain SHALL use SQLite FTS recall behavior
- **AND** the system SHALL still proceed when no FTS match is found

#### Scenario: Memory budget is enforced

- **WHEN** hybrid recall returns more candidate memories than fit in `memory_token_budget`
- **THEN** the Memory brain SHALL include the highest-ranked snippets first
- **AND** lower-ranked snippets SHALL be omitted rather than exceeding the budget

### Requirement: Memory index supports fast recall

The Memory brain SHALL maintain a SQLite FTS index for L1 and searchable L2 content. The index SHALL remain the fast exact-match source for both FTS mode and the FTS branch of hybrid mode, while hybrid mode MAY additionally score indexed L1/L2 text with local lexical/semantic ranking.

#### Scenario: L1 record is written

- **WHEN** a new L1 memory file is created or updated
- **THEN** the indexer SHALL upsert the record into `memory/index.sqlite`
- **AND** `before_chat` search SHALL query the index instead of scanning all files for exact-match recall

#### Scenario: Hybrid recall uses indexed records

- **WHEN** hybrid recall runs
- **THEN** the system SHALL use indexed L1/L2 records as the candidate source
- **AND** it SHALL NOT perform an unbounded full directory walk during chat assembly

#### Scenario: Unsafe FTS query characters

- **WHEN** a user query contains punctuation or characters that would make SQLite FTS `MATCH` fail
- **THEN** the Memory search layer SHALL sanitize or safely handle the query
- **AND** chat assembly SHALL continue without throwing an FTS syntax error
