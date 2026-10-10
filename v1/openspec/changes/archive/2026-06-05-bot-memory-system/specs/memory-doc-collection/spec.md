## ADDED Requirements

### Requirement: Long document storage in category folders

The system SHALL store user-collected long texts under `{soul_folder}/memory/docs/{slug}/` with `meta.json` (title, source, tags, summary, timestamp) and `chunk-*.md` files (typically 800–1500 characters per chunk). Full article text MUST NOT be written into `memory.md` or injected wholesale into the system prompt. Chunk metadata SHALL also be indexed in `memory/index.sqlite`.

#### Scenario: User collects an article

- **WHEN** the user explicitly requests to remember an article or long passage (manual action or API)
- **THEN** the system SHALL create `memory/docs/{slug}/meta.json`
- **AND** SHALL split body text into `chunk-001.md`, `chunk-002.md`, etc.
- **AND** SHALL update the FTS index for chunk search
- **AND** SHALL NOT copy the full text into `memory.md`

#### Scenario: Default chat without doc intent

- **WHEN** the user sends a normal message without document-related intent
- **THEN** document chunks SHALL NOT be injected into the prompt by default

### Requirement: Intent-gated chunk retrieval via search program

Long document chunks SHALL only be retrieved through `search_memory()` when the user message matches document-related intent (keyword rules in Phase 1).

#### Scenario: Style or reference question

- **WHEN** the user asks to write in a preferred style or references a previously saved article (intent matched)
- **THEN** the backend SHALL FTS-search indexed chunks for the active bot
- **AND** SHALL inject only the top relevant chunks within the shared memory token budget
- **AND** SHALL NOT inject unrelated chunks or entire `docs/` folders

#### Scenario: Unrelated question

- **WHEN** the user asks a factual question unrelated to saved documents
- **THEN** chunk retrieval SHALL be skipped
- **AND** only `memory_items` retrieval may run

### Requirement: Boundary with knowledge folder

Static knowledge in `souls/{id}/knowledge/*.md` and user-collected documents in `memory/docs/` SHALL remain separate. The system SHALL NOT duplicate the same long text into both without user action.

#### Scenario: Soul knowledge load

- **WHEN** the system loads the soul folder at startup
- **THEN** `knowledge/*.md` SHALL continue to load in full as static knowledge
- **AND** collected documents SHALL remain in `memory/docs/` and SHALL only enter the prompt via search retrieval

### Requirement: Quote-type items in items/quote folder

Short favorite phrases and expressions SHALL be stored under `memory/items/quote/` as individual files in Phase 1. They SHALL be indexed and follow the same retrieval rules as other items, with minimal recency decay.

#### Scenario: User saves a favorite sentence

- **WHEN** the user saves a short quote or catchphrase
- **THEN** the system SHALL store a file under `memory/items/quote/`
- **AND** SHALL index it for FTS search
- **AND** SHALL allow retrieval when the user asks for style or phrasing help

### Requirement: Manual collection in Phase 1

Automatic ingestion of long texts from every assistant reply SHALL NOT be enabled in Phase 1. Collection SHALL require explicit user action (UI button, command, or dedicated API).

#### Scenario: Assistant outputs long text

- **WHEN** the assistant generates a long article in chat
- **THEN** the system SHALL NOT automatically chunk and store it under `memory/docs/`
- **UNLESS** the user explicitly chooses「收藏」or equivalent
