## MODIFIED Requirements

### Requirement: L1 atomic memory extraction

The Memory brain SHALL extract atomic memories from completed turns using the bot's resolved background model when an LLM is required.

#### Scenario: L1 extraction runs after a turn

- **WHEN** `l1_extract_every_turn` is true or the turn is queued for batch extraction
- **THEN** the system SHALL create or update L1 records typed as fact, preference, constraint, or todo
- **AND** each L1 record SHALL reference its source turn or L0 evidence id
- **AND** LLM extraction SHALL use `background_model` when configured
