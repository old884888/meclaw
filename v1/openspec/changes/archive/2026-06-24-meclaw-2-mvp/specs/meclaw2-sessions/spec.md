## ADDED Requirements

### Requirement: Sessions scoped to bot

Each chat session SHALL belong to exactly one `bot_id`.

#### Scenario: New session under bot

- **WHEN** the user creates a new conversation from Bot B's session list
- **THEN** the new session record SHALL have `bot_id` equal to B

### Requirement: Session index and message files

The system SHALL maintain `history/sessions.json` for metadata and `history/{session-id}.json` for messages.

#### Scenario: User switches session

- **WHEN** the user selects a different session under the same Bot
- **THEN** the UI SHALL load messages from that session's message file
- **AND** other sessions' messages SHALL remain unchanged on disk

### Requirement: Session title from first message

The system SHALL update session title from the first user message snippet when title is empty.

#### Scenario: First message sent

- **WHEN** the user sends the first message in a new session
- **THEN** the session title SHALL be derived from that message for sidebar display

### Requirement: Session title normalization

Automatically generated session titles SHALL be normalized and length-limited.

#### Scenario: First message has long multi-line text

- **WHEN** the first user message contains newlines or more than thirty display characters
- **THEN** the session title SHALL remove line breaks
- **AND** the title SHALL be truncated to a short readable snippet

#### Scenario: First message content is empty after trimming

- **WHEN** the system needs a title but the content is empty
- **THEN** the session title SHALL be `新对话`

### Requirement: Delete session

The user SHALL be able to delete a session and its message file.

#### Scenario: User deletes session

- **WHEN** the user confirms deletion of a session
- **THEN** the session SHALL be removed from `sessions.json`
- **AND** the corresponding message file SHALL be deleted

### Requirement: Message schema

Session message files SHALL store messages with stable ids, role, content, created_at, and optional status.

#### Scenario: Assistant response is saved

- **WHEN** an assistant message is persisted
- **THEN** it SHALL include `id`, `role`, `content`, `created_at`, and `status`
- **AND** `status` SHALL be one of `done`, `stopped`, or `error`

#### Scenario: User message is saved

- **WHEN** a user message is persisted
- **THEN** it SHALL include `id`, `role`, `content`, and `created_at`

### Requirement: Minimum one bot for meaningful use

The application SHALL allow multiple sessions per Bot but SHALL NOT require global session list without Bot context.

#### Scenario: Sidebar session list

- **WHEN** the user views sessions
- **THEN** sessions SHALL only be listed in the context of a selected Bot
