# bot-centric-sidebar Specification

## Purpose
TBD - created by archiving change bot-centric-navigation. Update Purpose after archive.
## Requirements
### Requirement: Bot list as sidebar first level

The chat sidebar SHALL display a Bot list as the first navigation level when the user opens the 「对话」 tab and no Bot drill-down is active.

#### Scenario: User opens chat sidebar

- **WHEN** the user views the chat sidebar in default state
- **THEN** the UI SHALL list all configured Bots (not a flat global session list)
- **AND** each Bot row SHALL show at minimum avatar and name
- **AND** Bots SHALL be ordered by the most recent `updated_at` among their sessions (descending), with Bots without sessions listed after named Bots

### Requirement: Bot session drill-down

The user SHALL drill into a Bot to see only that Bot's sessions.

#### Scenario: User selects a Bot

- **WHEN** the user clicks a Bot in the first-level list
- **THEN** the sidebar SHALL show only sessions where `session.bot_id` equals that Bot's id
- **AND** sessions SHALL be sorted by `updated_at` descending
- **AND** a back control SHALL return to the Bot list

### Requirement: New session scoped to selected Bot

New sessions SHALL be created only from a Bot's session list and SHALL belong to that Bot.

#### Scenario: User creates a new conversation under a Bot

- **WHEN** the user clicks 「+ 新建对话」 while viewing a Bot's session list
- **THEN** the backend SHALL create a session with `bot_id` set to that Bot
- **AND** the new session SHALL NOT be creatable from the Bot list first level (no global new button there)

### Requirement: Bot locked for active session

While a session is open, the user SHALL NOT switch Bot identity for that session.

#### Scenario: User has an open session

- **WHEN** `currentSessionId` refers to an existing session with a non-empty `bot_id`
- **THEN** the header Bot selector SHALL be read-only (display only)
- **AND** attempting `switch_bot` to a different Bot while that session is active SHALL be rejected or ignored

### Requirement: Session card displays Bot identity

Each session card in a Bot's session list SHALL show Bot identity and mode indicator.

#### Scenario: Session list rendering

- **WHEN** the UI renders a session under a Bot
- **THEN** the card SHALL show Bot avatar, Bot name, and a DeepSeek reply-mode badge (思考 or 快速) when applicable
- **AND** the card SHALL show title, relative time, and message count

### Requirement: Search results grouped by Bot

Session search results SHALL be grouped by Bot.

#### Scenario: User searches conversations

- **WHEN** the user enters a search keyword
- **THEN** results SHALL be grouped under Bot headings (including a dedicated legacy group when applicable)
- **AND** each result SHALL remain openable via `switch_session`

### Requirement: Multi-select delete in Bot session list only

Bulk delete SHALL be available only in a Bot's session list view.

#### Scenario: User bulk-deletes sessions

- **WHEN** the user enables multi-select mode
- **THEN** it SHALL only be available while viewing a Bot's session list (or legacy session list)
- **AND** deletion SHALL not be offered from the Bot list first level

### Requirement: Empty Bot state

A Bot with no sessions SHALL show an empty state with a call to action.

#### Scenario: User opens a Bot with zero sessions

- **WHEN** the user drills into a Bot that has no sessions
- **THEN** the UI SHALL show an empty state
- **AND** offer 「和它开始第一个对话」 which creates the first session for that Bot

### Requirement: Legacy sessions without bot_id

Sessions with missing or empty `bot_id` SHALL appear in a separate legacy section.

#### Scenario: Legacy session exists

- **WHEN** a session has no `bot_id`
- **THEN** it SHALL NOT appear under any Bot's session list
- **AND** it SHALL appear under a 「历史遗留」 entry on the Bot list level
- **AND** the system SHALL NOT auto-assign `bot_id` during migration

