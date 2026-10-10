# meclaw2-memory-port Specification

## Purpose

MemoryService abstraction and bot-scoped memory directories for MeClaw 2.0 / MNEMOS multi-brain integration.

## Requirements

### Requirement: Memory service abstraction

The backend SHALL define a `MemoryService` interface used by the Multi-Brain Orchestrator with hooks for before-chat, after-turn, and compress.

#### Scenario: Chat assembly with multi-brain enabled

- **WHEN** the server builds messages for an API call and `multi_brain_enabled` is true
- **THEN** it SHALL invoke the Memory brain through `before_chat` on the configured memory service
- **AND** the returned block SHALL be budgeted and MAY be empty when retrieval is disabled

#### Scenario: MVP chat assembly with multi-brain disabled

- **WHEN** `multi_brain_enabled` is false
- **THEN** chat assembly MAY skip memory hooks
- **AND** chat SHALL complete successfully without memory-related errors

### Requirement: No-op implementation remains available

A no-op memory service implementation SHALL remain available for tests and disabled configurations.

#### Scenario: Memory disabled in config

- **WHEN** `memory_enabled` is false
- **THEN** chat SHALL complete successfully without memory storage side effects beyond placeholders

### Requirement: Memory config placeholders

`config.json` SHALL include multi-brain and memory budget fields for orchestrator use.

#### Scenario: Default config

- **WHEN** a fresh 2.0 data directory is initialized
- **THEN** config SHALL include `multi_brain_enabled`, brain toggles, `memory_token_budget`, `persona_token_budget`, compaction thresholds, and learner schedule fields
- **AND** safe defaults SHALL keep learner and expensive extraction off or minimal where appropriate

### Requirement: After-turn hook without blocking

The system SHALL call `after_turn` asynchronously after a completed turn without blocking the WebSocket response.

#### Scenario: Turn completes with memory write enabled

- **WHEN** assistant generation finishes
- **THEN** `after_turn` SHALL be scheduled
- **AND** L0 persistence and queued L1 extraction SHALL not delay the final WebSocket event

### Requirement: Soul memory directory reserved

Each bot soul folder SHALL contain a `memory/` directory created at bot creation time for bot-scoped personal memory files.

#### Scenario: Inspect filesystem after bot create

- **WHEN** a bot is created
- **THEN** `souls/{bot-id}/memory/` SHALL exist
- **AND** chat MAY work before any memory files are populated
