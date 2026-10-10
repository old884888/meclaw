## MODIFIED Requirements

### Requirement: Bot stores optional per-brain configuration

Each bot in `config.json` MAY include a `brains` object and optional `background_model` field. The effective configuration SHALL be visible through super brain status.

#### Scenario: Bot without per-brain overrides

- **WHEN** a bot has no `brains` field
- **THEN** multi-brain behavior SHALL use global default settings from `config.json`
- **AND** chat SHALL behave the same as before this change
- **AND** super brain status SHALL indicate the configuration source as global/default

#### Scenario: Bot overrides memory budget only

- **WHEN** a bot sets `brains.memory_token_budget` but leaves other brain fields unset
- **THEN** the orchestrator SHALL use the bot value for memory budget
- **AND** SHALL inherit all other brain settings from global defaults
- **AND** super brain status SHALL show the effective budget and that the Bot has an override

### Requirement: Background model resolves separately from executor model

Each bot MAY specify `background_model` for offline or auxiliary LLM tasks, and super brain status SHALL display both executor and background model resolution.

#### Scenario: Background model is configured

- **WHEN** a bot has `background_model` set to a valid model in its bound profile
- **THEN** Tier3 summarization and L1 extraction SHALL use `background_model`
- **AND** main chat streaming SHALL continue to use the bot's primary `model`
- **AND** status SHALL display executor and background model labels separately

#### Scenario: Background model is empty

- **WHEN** `background_model` is empty or omitted
- **THEN** background LLM tasks SHALL fall back to the bot's primary `model`
- **AND** status SHALL indicate that background model inherits the main model

### Requirement: Effective Bot brain state is status-addressable

The backend SHALL expose effective Bot brain state for read-only UI surfaces.

#### Scenario: Status endpoint summarizes Bot brains

- **WHEN** `/api/bots/{bot_id}/brain/status` is requested
- **THEN** the response SHALL include effective enabled flags and budgets for Persona, Memory, Cognitive, and Learner brains
- **AND** values SHALL match the same merge logic used during chat assembly

#### Scenario: Bot becomes unready

- **WHEN** a provider is disabled, missing, or lacks a valid model
- **THEN** super brain status SHALL surface the same readiness message as the Bot card
- **AND** Executor SHALL be shown as unavailable or error
