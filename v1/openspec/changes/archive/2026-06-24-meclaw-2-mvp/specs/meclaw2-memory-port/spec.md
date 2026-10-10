## ADDED Requirements

### Requirement: Memory service abstraction

The backend SHALL define a `MemoryService` interface used by chat assembly with hooks for before-chat, after-turn, and compress.

#### Scenario: MVP chat assembly

- **WHEN** the server builds messages for an API call
- **THEN** it SHALL invoke `before_chat` on the configured memory service
- **AND** the returned block MAY be empty in MVP

### Requirement: No-op implementation in MVP

The default memory service implementation SHALL perform no storage and return empty injection text.

#### Scenario: Memory disabled in config

- **WHEN** `memory_enabled` is false
- **THEN** chat SHALL complete successfully without memory-related errors
- **AND** no memory files SHALL be created beyond directory placeholders

### Requirement: Memory config placeholders

`config.json` SHALL include `memory_enabled`, `memory_retrieval_enabled`, `memory_write_enabled`, and `memory_token_budget` fields for future use.

#### Scenario: Default config

- **WHEN** a fresh 2.0 data directory is initialized
- **THEN** memory flags SHALL default to disabled or zero budget
- **AND** the settings UI MAY show memory as upcoming

#### Scenario: Config schema is written

- **WHEN** default config is created
- **THEN** `memory_token_budget` SHALL be present with a numeric default
- **AND** memory flags SHALL be present even though the MVP implementation is NoOp

### Requirement: After-turn hook without blocking

The system SHALL call `after_turn` asynchronously after a completed turn without blocking the WebSocket response.

#### Scenario: Turn completes

- **WHEN** assistant generation finishes
- **THEN** `after_turn` SHALL be scheduled
- **AND** MVP NoOp SHALL return immediately without side effects

### Requirement: Soul memory directory reserved

Each bot soul folder SHALL contain a `memory/` directory created at bot creation time.

#### Scenario: Inspect filesystem after bot create

- **WHEN** a bot is created
- **THEN** `souls/{bot-id}/memory/` SHALL exist
- **AND** MVP SHALL NOT require files inside it for chat to work
