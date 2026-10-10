## ADDED Requirements

### Requirement: Memory list APIs for L0 and L2

The Memory brain SHALL expose HTTP list endpoints for L0 evidence and L2 session summaries.

#### Scenario: Client lists L0 evidence

- **WHEN** `GET /api/bots/{bot_id}/memory/l0` is called
- **THEN** the API SHALL return paginated L0 evidence items for that Bot
- **AND** it MAY filter by `session_id` when provided

#### Scenario: Client lists L2 summaries

- **WHEN** `GET /api/bots/{bot_id}/memory/l2` is called
- **THEN** the API SHALL return session summaries associated with that Bot
- **AND** each item SHALL include session id, title, summary excerpt, and updated time when available

### Requirement: Memory search API

The Memory brain SHALL expose a search endpoint for Bot-scoped memory retrieval.

#### Scenario: Client searches memory

- **WHEN** `GET /api/bots/{bot_id}/memory/search?q=...` is called with a non-empty query
- **THEN** the API SHALL return ranked memory hits using the existing index/search implementation
- **AND** each hit SHALL include type, snippet, and source session when available

#### Scenario: Search query is empty

- **WHEN** the search query is missing or blank
- **THEN** the API SHALL return an empty result set or a 400 with a clear message

## MODIFIED Requirements

### Requirement: L1 atomic memory extraction

The Memory brain SHALL extract atomic memories from completed turns using the bot's resolved background model when an LLM is required.

#### Scenario: L1 extraction runs after a turn

- **WHEN** `l1_extract_every_turn` is true or the turn is queued for batch extraction
- **THEN** the system SHALL create or update L1 records typed as fact, preference, constraint, or todo
- **AND** each L1 record SHALL reference its source turn or L0 evidence id
- **AND** LLM extraction SHALL use `background_model` when configured
- **AND** listed L1 records SHALL be readable via `GET /api/bots/{bot_id}/memory/l1` for UI consumption
