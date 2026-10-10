# group-chat

Multi-Bot group conversations with @-mention reply routing and isolated group memory.

## ADDED Requirements

### Requirement: Group chat sidebar tab

The application SHALL provide a dedicated 「群聊」 sidebar tab separate from private 「对话」 navigation.

#### Scenario: User switches to group tab

- **WHEN** the user selects the group chat tab
- **THEN** the sidebar SHALL show a group list (not the Bot private chat list)
- **AND** the user SHALL drill into a group to see that group's sessions

### Requirement: Group entity with member Bots

The system SHALL allow creating groups that contain multiple Bots.

#### Scenario: User creates a group

- **WHEN** the user creates a group with selected member Bots
- **THEN** the group SHALL be persisted with a unique `group_id` and `member_bot_ids`
- **AND** the group SHALL support multiple conversation sessions under it

### Requirement: At-mention required for Bot reply

In group chat, a Bot SHALL reply only when explicitly mentioned by the user.

#### Scenario: User sends message without mention

- **WHEN** the user sends a message in a group session without @-mentioning a member Bot
- **THEN** the message SHALL be accepted and stored in the session history
- **AND** no member Bot SHALL generate a reply automatically
- **AND** the send action SHALL NOT be blocked

#### Scenario: User mentions a Bot via member picker

- **WHEN** the user triggers @ in the group composer (e.g. types `@` or clicks an @ control)
- **THEN** the UI SHALL show a selectable list of group member Bots
- **AND** the user SHALL pick a member from the list rather than relying on free-text name entry alone

#### Scenario: User mentions a Bot

- **WHEN** the user @-mentions a specific member Bot via the picker
- **THEN** only that Bot SHALL generate the reply for that message
- **AND** the reply SHALL use that Bot's persona (`soul.md` etc.)

### Requirement: Isolated group memory store

Group conversations SHALL use a dedicated memory directory separate from Bot private memory.

#### Scenario: Memory write in group session

- **WHEN** memory extraction or user collection occurs in a group session
- **THEN** writes SHALL go to `groups/{group_id}/memory/`
- **AND** SHALL NOT automatically duplicate into `souls/{bot_id}/memory/`

#### Scenario: Memory retrieval in private chat

- **WHEN** the user asks a Bot in private chat about remembered facts
- **THEN** retrieval SHALL search only that Bot's `souls/{bot_id}/memory/`
- **AND** SHALL NOT search group memory unless explicitly specified in a future feature

#### Scenario: Memory retrieval in group chat

- **WHEN** a mentioned Bot replies in a group session
- **THEN** optional group memory retrieval SHALL search `groups/{group_id}/memory/` within token budget

### Requirement: Memory organizer agent configuration

The settings UI SHALL allow configuring an optional memory compression/organization agent.

#### Scenario: User enables memory organizer

- **WHEN** the user enables memory organization settings
- **THEN** they SHALL specify an organizer API profile for LLM calls
- **AND** they MAY optionally specify an organizer Bot whose persona (`soul.md`) is used only in the organizer system prompt
- **AND** the organizer Bot SHALL NOT replace the API profile endpoint for compression or extraction calls
