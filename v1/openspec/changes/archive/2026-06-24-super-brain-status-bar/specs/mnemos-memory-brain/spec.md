## MODIFIED Requirements

### Requirement: Memory brain owns personal conversation storage

The Memory brain SHALL own L0-L3 personal conversation memory for a bot scope and SHALL provide lightweight read-only statistics for the super brain status UI.

#### Scenario: Turn is completed with memory write enabled

- **WHEN** `memory_write_enabled` is true and a turn completes
- **THEN** the Memory brain SHALL persist L0 evidence for the completed turn
- **AND** L0 SHALL retain enough data to trace back to the original user and assistant messages

#### Scenario: Status requests memory stats

- **WHEN** `/api/bots/{bot_id}/brain/status` requests memory statistics
- **THEN** the Memory brain or helper SHALL return counts for L0, L1, L2, and L3 availability
- **AND** statistics SHALL be computed without reading full large memory bodies

### Requirement: Memory index supports fast recall

The Memory brain SHALL maintain a SQLite FTS index for L1 and searchable L2 content, and status SHALL expose whether that index is available.

#### Scenario: L1 record is written

- **WHEN** a new L1 memory file is created or updated
- **THEN** the indexer SHALL upsert the record into `memory/index.sqlite`
- **AND** `before_chat` search SHALL query the index instead of scanning all files

#### Scenario: Status checks memory index

- **WHEN** memory status is requested
- **THEN** the response SHALL include `index_status`
- **AND** `index_status` SHALL be one of `ready`, `missing`, or `error`

### Requirement: Memory status exposes recent activity

The Memory brain SHALL expose recent read/write activity when available.

#### Scenario: L0 evidence is written

- **WHEN** a turn is saved to L0
- **THEN** status SHOULD expose a `last_write_at` timestamp derived from stored evidence metadata or file mtime

#### Scenario: Memory recall contributes to a turn

- **WHEN** Memory brain recall contributes a prompt block
- **THEN** trace SHOULD expose the number of recalled snippets
- **AND** status SHALL use that value as `last_recall_count` for the active session when available

### Requirement: Memory status is fault-tolerant

Memory status SHALL never prevent chat from working.

#### Scenario: Memory directory is missing

- **WHEN** the Bot memory directory does not exist yet
- **THEN** memory stats SHALL return zero counts and `index_status = "missing"`
- **AND** the status API SHALL still return `ok: true`

#### Scenario: A memory file is malformed

- **WHEN** a memory stats helper encounters unreadable or malformed files
- **THEN** it SHALL skip those files for counting
- **AND** include a non-fatal warning or `last_error` value when practical
