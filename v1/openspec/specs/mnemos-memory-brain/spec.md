# mnemos-memory-brain Specification

## Purpose

Personal conversation memory (L0–L3) for MNEMOS bots: evidence storage, atomic extraction, session summaries, profile snippets, and FTS recall.
## Requirements
### Requirement: Memory brain owns personal conversation storage

The Memory brain SHALL own L0–L3 personal conversation memory for a bot scope.

#### Scenario: Turn is completed with memory write enabled

- **WHEN** `memory_write_enabled` is true and a turn completes
- **THEN** the Memory brain SHALL persist L0 evidence for the completed turn
- **AND** L0 SHALL retain enough data to trace back to the original user and assistant messages

### Requirement: L1 atomic memory extraction

The Memory brain SHALL extract atomic memories from completed turns. Each L1 record SHALL receive a `topic_key` using regex-first assignment and, when enabled, embedding-based topic clustering fallback.

#### Scenario: L1 extraction runs after a turn

- **WHEN** `l1_extract_every_turn` is true or the turn is queued for batch extraction
- **THEN** the system SHALL create or update L1 records typed as fact, preference, constraint, or todo
- **AND** each L1 record SHALL reference its source turn or L0 evidence id
- **AND** each L1 record SHALL receive a stable `topic_key` suitable for preference evolution chains

### Requirement: L2 session summary maintenance

The Memory brain SHALL maintain a running session summary for long conversations.

#### Scenario: Session reaches update interval

- **WHEN** turn count since last L2 update reaches `l2_update_every_n_turns`
- **THEN** the Memory brain SHALL update the session summary with progress, open todos, and key decisions
- **AND** the summary SHALL be retrievable for the current session without loading full history

### Requirement: L3 user profile is a compressed long-term persona input

The Memory brain SHALL maintain an L3 user profile used by the Persona brain and/or Memory brain as a short injected summary. When consolidation is enabled and profile capacity is exceeded, the system SHALL compress the profile while preserving pinned constraints and newer preferences.

#### Scenario: Profile exists for a bot scope

- **WHEN** `before_chat` runs
- **THEN** the Persona brain SHALL receive a bounded excerpt derived from L3
- **AND** the excerpt SHALL NOT exceed `persona_token_budget`

#### Scenario: Profile is missing but memory exists

- **WHEN** L1 or L2 memory exists for a bot
- **AND** no L3 profile exists
- **THEN** the Memory brain SHALL be able to generate an initial L3 profile from existing memory records
- **AND** chat SHALL still proceed if generation is skipped or fails

#### Scenario: Profile is refreshed

- **WHEN** the configured L3 update interval is reached or a manual refresh is requested
- **THEN** the Memory brain SHALL update the L3 profile from current L1/L2 memory
- **AND** the profile SHALL include last-updated metadata or equivalent traceability

#### Scenario: Preference evolves

- **WHEN** newer L1 memories conflict with older preferences
- **THEN** the L3 profile SHALL prefer the newer active preference in the injected summary
- **AND** older evidence SHALL remain traceable in L1/L0 rather than being deleted automatically

#### Scenario: Soul remains human-authored

- **WHEN** L3 profile is generated or refreshed
- **THEN** `soul.md` SHALL NOT be modified automatically
- **AND** generated profile content SHALL remain under the bot memory directory

#### Scenario: Profile capacity triggers consolidation

- **WHEN** profile content exceeds configured capacity threshold
- **AND** consolidation is enabled
- **THEN** the system SHALL compress redundant profile entries
- **AND** SHALL retain constraint-type facts at full fidelity

### Requirement: before_chat recall is budgeted and layered

Hybrid recall SHALL apply a composite ranking score combining relevance, importance, recency decay, and hit-count boost. Atoms marked `superseded_by` SHALL be excluded from direct hit injection unless required for an explicit evolution-chain block.

#### Scenario: Superseded atoms filtered from hits

- **WHEN** hybrid search returns candidate atoms
- **AND** an atom has a non-empty `superseded_by` field
- **THEN** that atom SHALL NOT appear as a standalone hit snippet
- **AND** it MAY still appear inside a topic evolution chain when routed

#### Scenario: Recalled atoms gain hit count

- **WHEN** an L1 atom is injected into the memory block during `before_chat`
- **THEN** the system SHALL increment that atom's `hit_count` best-effort
- **AND** chat SHALL proceed if the increment fails

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

### Requirement: Soft delete preserves auditability

Memory records SHALL support soft delete with audit metadata.

#### Scenario: User or system deletes a memory item

- **WHEN** a delete operation is requested
- **THEN** the record SHALL be marked deleted with timestamp and reason
- **AND** physical content SHALL remain recoverable from archive paths or audit logs
- **AND** soft-deleted records SHALL NOT appear in default recall results

### Requirement: Memory brain does not replace soul files

The Memory brain SHALL store learned user-specific facts separately from `soul.md`.

#### Scenario: L3 profile is updated

- **WHEN** learner or extraction updates L3
- **THEN** `soul.md` SHALL NOT be modified automatically
- **AND** Soul remains the human-authored identity baseline

### Requirement: L3 profile is inspectable and budgeted

The L3 user profile SHALL be stored in a human-readable form and injected only as a bounded excerpt.

#### Scenario: User inspects generated profile

- **WHEN** the user opens the bot memory directory
- **THEN** the L3 profile SHALL be readable without direct SQLite inspection
- **AND** it SHALL summarize durable preferences, constraints, style preferences, recurring projects, or todos when present

#### Scenario: Profile exceeds budget

- **WHEN** the L3 profile is longer than the available persona or memory budget
- **THEN** the system SHALL inject the highest-priority profile sections first
- **AND** lower-priority details SHALL be omitted rather than exceeding budget

