## ADDED Requirements

### Requirement: Bot CRUD

The system SHALL allow creating, listing, updating, and deleting Bots.

#### Scenario: User creates second bot

- **WHEN** the user creates a new Bot with name and avatar
- **THEN** a new Bot id SHALL be assigned
- **AND** a corresponding `souls/{bot-id}/` directory SHALL be created

### Requirement: Default bot bootstrap

The system SHALL create a default Bot when no Bots exist during first-run bootstrap.

#### Scenario: Empty config starts

- **WHEN** `config.json` has no Bots
- **THEN** the backend SHALL create a default Bot with a soul folder
- **AND** the UI SHALL show that Bot in the Bot list

### Requirement: Soul folder per bot

Each Bot SHALL have soul content stored at `souls/{bot-id}/soul.md` under the data root.

#### Scenario: User edits soul

- **WHEN** the user saves soul text for a Bot
- **THEN** the content SHALL be written to that Bot's `soul.md`
- **AND** subsequent chat SHALL inject the updated soul in the system prompt

### Requirement: Optional constraints file

The system MAY load `souls/{bot-id}/constraints.md` when present and append to the system prompt.

#### Scenario: Constraints exist

- **WHEN** `constraints.md` exists for the active Bot
- **THEN** its content SHALL be included in the system layer for chat

### Requirement: Bot parameter overrides

A Bot MAY override profile `model`, `temperature`, and `max_tokens` when non-empty.

#### Scenario: Bot sets custom model

- **WHEN** a Bot has `model` set to `deepseek-chat` and profile default is different
- **THEN** chat for that Bot SHALL use `deepseek-chat`

### Requirement: Memory directory placeholder

Each new Bot soul directory SHALL include an empty `memory/` subdirectory for future memory features.

#### Scenario: Bot created

- **WHEN** a Bot is created
- **THEN** `souls/{bot-id}/memory/` SHALL exist on disk
- **AND** MVP chat SHALL NOT write memory entries into it

### Requirement: Bot deletion preserves session integrity

The MVP SHALL prevent deleting a Bot that still has sessions.

#### Scenario: User deletes bot with sessions

- **WHEN** a Bot has one or more sessions in `history/sessions.json`
- **THEN** delete SHALL be rejected with a user-visible message
- **AND** the Bot soul directory SHALL remain on disk

#### Scenario: User deletes unused bot

- **WHEN** a Bot has no sessions
- **THEN** the Bot SHALL be removed from config
- **AND** its soul directory MAY be deleted or archived according to implementation policy
