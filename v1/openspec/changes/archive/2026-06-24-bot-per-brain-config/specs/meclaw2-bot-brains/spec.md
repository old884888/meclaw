## ADDED Requirements

### Requirement: Bot stores optional per-brain configuration

Each bot in `config.json` MAY include a `brains` object and optional `background_model` field.

#### Scenario: Bot without per-brain overrides

- **WHEN** a bot has no `brains` field
- **THEN** multi-brain behavior SHALL use global default settings from `config.json`
- **AND** chat SHALL behave the same as before this change

#### Scenario: Bot overrides memory budget only

- **WHEN** a bot sets `brains.memory_token_budget` but leaves other brain fields unset
- **THEN** the orchestrator SHALL use the bot value for memory budget
- **AND** SHALL inherit all other brain settings from global defaults

### Requirement: Background model resolves separately from executor model

Each bot MAY specify `background_model` for offline or auxiliary LLM tasks.

#### Scenario: Background model is configured

- **WHEN** a bot has `background_model` set to a valid model in its bound profile
- **THEN** Tier3 summarization and L1 extraction SHALL use `background_model`
- **AND** main chat streaming SHALL continue to use the bot's primary `model`

#### Scenario: Background model is empty

- **WHEN** `background_model` is empty or omitted
- **THEN** background LLM tasks SHALL fall back to the bot's primary `model`

### Requirement: Bot editor exposes per-brain settings

The Bot editor UI SHALL allow configuring per-bot brain overrides without duplicating global provider CRUD.

#### Scenario: User edits bot brains

- **WHEN** the user opens Bot edit and expands the brains section
- **THEN** the UI SHALL show brain toggles, budget fields, and background model selector
- **AND** empty fields SHALL indicate inheritance from global defaults

#### Scenario: User saves bot brains

- **WHEN** the user saves the bot editor
- **THEN** `brains` and `background_model` SHALL persist on the bot record
- **AND** subsequent chats with that bot SHALL use the merged effective configuration
