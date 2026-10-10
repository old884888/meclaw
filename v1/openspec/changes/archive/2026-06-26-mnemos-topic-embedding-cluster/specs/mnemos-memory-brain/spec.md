## MODIFIED Requirements

### Requirement: L1 atomic memory extraction

The Memory brain SHALL extract atomic memories from completed turns. Each L1 record SHALL receive a `topic_key` using regex-first assignment and, when enabled, embedding-based topic clustering fallback.

#### Scenario: L1 extraction runs after a turn

- **WHEN** `l1_extract_every_turn` is true or the turn is queued for batch extraction
- **THEN** the system SHALL create or update L1 records typed as fact, preference, constraint, or todo
- **AND** each L1 record SHALL reference its source turn or L0 evidence id
- **AND** each L1 record SHALL receive a stable `topic_key` suitable for preference evolution chains
