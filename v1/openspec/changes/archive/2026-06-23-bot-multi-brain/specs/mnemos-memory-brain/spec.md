## ADDED Requirements

### Requirement: Memory brain owns personal conversation storage

The Memory brain SHALL own L0–L3 personal conversation memory for a bot scope.

#### Scenario: Turn is completed with memory write enabled

- **WHEN** `memory_write_enabled` is true and a turn completes
- **THEN** the Memory brain SHALL persist L0 evidence for the completed turn
- **AND** L0 SHALL retain enough data to trace back to the original user and assistant messages

### Requirement: L1 atomic memory extraction

The Memory brain SHALL extract atomic memories from completed turns.

#### Scenario: L1 extraction runs after a turn

- **WHEN** `l1_extract_every_turn` is true or the turn is queued for batch extraction
- **THEN** the system SHALL create or update L1 records typed as fact, preference, constraint, or todo
- **AND** each L1 record SHALL reference its source turn or L0 evidence id

### Requirement: L2 session summary maintenance

The Memory brain SHALL maintain a running session summary for long conversations.

#### Scenario: Session reaches update interval

- **WHEN** turn count since last L2 update reaches `l2_update_every_n_turns`
- **THEN** the Memory brain SHALL update the session summary with progress, open todos, and key decisions
- **AND** the summary SHALL be retrievable for the current session without loading full history

### Requirement: L3 user profile is a compressed long-term persona input

The Memory brain SHALL maintain an L3 user profile used by the Persona brain as a short injected summary.

#### Scenario: Profile exists for a bot scope

- **WHEN** `before_chat` runs
- **THEN** the Persona brain SHALL receive a bounded excerpt derived from L3
- **AND** the excerpt SHALL NOT exceed `persona_token_budget`

### Requirement: before_chat recall is budgeted and layered

The Memory brain `before_chat` hook SHALL return only budgeted, high-priority memory for the current query.

#### Scenario: Default recall on a new message

- **WHEN** `memory_retrieval_enabled` is true
- **THEN** recall SHALL prioritize current session L2 summary, then L1 top-k matches, then optional cross-session L2 when routed
- **AND** recall SHALL NOT inject entire L0 archives by default

### Requirement: Memory index supports fast recall

The Memory brain SHALL maintain a SQLite FTS index for L1 and searchable L2 content.

#### Scenario: L1 record is written

- **WHEN** a new L1 memory file is created or updated
- **THEN** the indexer SHALL upsert the record into `memory/index.sqlite`
- **AND** `before_chat` search SHALL query the index instead of scanning all files

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
