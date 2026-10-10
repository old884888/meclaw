## ADDED Requirements

### Requirement: Bot editor centralizes Bot identity fields
The system SHALL provide a Bot editor modal that centralizes the Bot's identity and runtime configuration.

#### Scenario: User opens Bot editor
- **WHEN** the user creates a new Bot or edits an existing Bot
- **THEN** the system SHALL open a modal editor
- **AND** the modal SHALL expose fields for name and avatar
- **AND** the modal SHALL expose the Bot's provider binding and runtime override settings

### Requirement: Bot editor exposes provider binding separately from provider management
The Bot editor SHALL let the user choose an existing provider profile without duplicating provider CRUD.

#### Scenario: User binds a provider to a Bot
- **WHEN** the Bot editor renders the brain configuration section
- **THEN** the editor SHALL offer a selector of existing provider profiles
- **AND** the editor SHALL NOT require provider creation or provider editing inside the Bot modal
- **AND** the editor SHALL point users to global settings when provider setup is missing or needs changes

### Requirement: Bot editor exposes Soul and constraints together
The Bot editor SHALL allow editing the Bot's persona prompt and optional constraints in one place.

#### Scenario: User edits Bot personality
- **WHEN** the user opens the Bot editor for an existing or new Bot
- **THEN** the modal SHALL include an editable Soul field
- **AND** the modal SHALL include an editable optional constraints field
- **AND** saving the Bot SHALL persist both values for later chat prompt assembly

### Requirement: Bot editor supports optional runtime overrides
The Bot editor SHALL support Bot-specific overrides without forcing them.

#### Scenario: User leaves override fields empty
- **WHEN** the user does not enter model override, `temperature`, or `max_tokens`
- **THEN** the Bot SHALL inherit those values from its bound provider where applicable
- **AND** the editor SHALL preserve empty values as an intentional inheritance state

### Requirement: Bot editor communicates unconfigured brain state
The Bot editor SHALL clearly indicate when a Bot is not yet ready to chat due to provider setup.

#### Scenario: No provider is bound or available
- **WHEN** the Bot editor opens for a Bot without a usable provider binding
- **THEN** the editor SHALL show that the Bot has no configured brain
- **AND** the UI SHALL explain that provider setup happens in global settings
- **AND** the saved Bot SHALL remain distinguishable from a fully chat-ready Bot

### Requirement: Saving Bot edits updates the launcher and chat entry state
Changes made in the Bot editor SHALL be reflected consistently in the launcher and subsequent chat entry.

#### Scenario: User saves Bot changes
- **WHEN** the user saves edits to Bot identity, provider binding, or prompt fields
- **THEN** the launcher SHALL reflect updated Bot display data
- **AND** subsequent entry into that Bot's workspace SHALL use the updated provider binding and prompt configuration
