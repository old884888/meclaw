## ADDED Requirements

### Requirement: Bot memory browser exposes L0-L3 content

MNEMOS SHALL provide a read-only memory browser UI scoped to the current Bot.

#### Scenario: User opens memory browser from status panel

- **WHEN** the user clicks a memory layer count or "查看记忆库" in the super brain status panel
- **THEN** the memory browser SHALL open for the current Bot
- **AND** it SHALL default to the tab matching the clicked layer when applicable

#### Scenario: User switches memory tabs

- **WHEN** the memory browser is open
- **THEN** the UI SHALL provide tabs for L0 evidence, L1 atoms, L2 session summaries, and L3 profile
- **AND** each tab SHALL load content from the corresponding API

#### Scenario: Bot has no memory data

- **WHEN** all memory layers are empty
- **THEN** the browser SHALL show a friendly empty state per tab
- **AND** the UI SHALL NOT show errors

### Requirement: L1 atoms can be deleted from the browser

The memory browser SHALL allow soft-deleting L1 atoms.

#### Scenario: User deletes an L1 atom

- **WHEN** the user confirms deletion of an L1 item
- **THEN** the frontend SHALL call `DELETE /api/bots/{bot_id}/memory/l1/{atom_id}`
- **AND** refresh the L1 list and super brain status memory counts

### Requirement: L2 summaries link to sessions

The L2 tab SHALL display session titles and summary excerpts.

#### Scenario: User clicks an L2 item

- **WHEN** the user selects an L2 session summary row
- **THEN** the UI SHALL switch to that session in the chat workspace when possible
- **AND** close or minimize the memory browser

### Requirement: L3 profile is read-only in the browser

The L3 tab SHALL display the user profile as read-only Markdown.

#### Scenario: L3 profile is missing

- **WHEN** no L3 profile exists for the Bot
- **THEN** the L3 tab SHALL show an empty state explaining that the profile is not yet configured

### Requirement: Memory search is available in the browser

The memory browser SHALL support searching Bot memory.

#### Scenario: User searches memory

- **WHEN** the user enters a search query
- **THEN** the frontend SHALL call `GET /api/bots/{bot_id}/memory/search?q=...`
- **AND** display ranked results with type and snippet
