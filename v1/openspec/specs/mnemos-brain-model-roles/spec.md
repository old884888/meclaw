# mnemos-brain-model-roles Specification

## Purpose
TBD - created by archiving change mnemos-brain-model-roles. Update Purpose after archive.
## Requirements
### Requirement: Models are bindable per role

The system SHALL allow binding a model (provider profile + model name) to each task role: `executor`, `extraction`, `summary`, `embedding`, and `rerank`.

#### Scenario: Role has an explicit binding

- **WHEN** a role is bound to a provider profile and model
- **THEN** tasks for that role SHALL use the bound model
- **AND** the binding SHALL be inspectable in the brain status view

#### Scenario: Role binding is empty

- **WHEN** a role has no explicit binding
- **THEN** the system SHALL resolve the role through a defined fallback chain
- **AND** resolution SHALL never fail when at least the executor model is configured

### Requirement: Role resolution has a deterministic fallback chain

The system SHALL resolve unbound roles via a deterministic fallback chain so existing behavior is preserved when roles are unconfigured.

#### Scenario: Extraction and summary fall back

- **WHEN** `extraction` or `summary` has no explicit binding
- **THEN** the role SHALL fall back to the background model when present, otherwise to the executor model

#### Scenario: Unconfigured roles preserve current behavior

- **WHEN** no role bindings are configured
- **THEN** chat, extraction, and summary SHALL behave exactly as the current executor/background two-tier behavior
- **AND** no role binding SHALL be required for a successful reply

### Requirement: Role bindings support global default and bot override

Role bindings SHALL be configurable as a global default and overridable per bot.

#### Scenario: Bot overrides a role

- **WHEN** a bot defines a role binding override
- **THEN** that bot SHALL use the overridden model for that role
- **AND** other bots SHALL continue to use the global default

#### Scenario: Bot inherits global roles

- **WHEN** a bot does not override a role
- **THEN** the bot SHALL inherit the global role binding (or its fallback)

### Requirement: Embedding and rerank roles use the same binding system

The `embedding` and `rerank` roles SHALL be configured through the same role-binding system rather than separate ad-hoc fields.

#### Scenario: Embedding role is configured

- **WHEN** the `embedding` role is bound or set to a local/off mode
- **THEN** the embedding port SHALL use that configuration
- **AND** the configuration surface SHALL be consistent with other roles

#### Scenario: Role implementation is absent

- **WHEN** a role (e.g., `rerank`) has a binding but no active implementation in the current build
- **THEN** the binding SHALL be retained as configuration without raising
- **AND** the system SHALL behave as if that role is disabled

