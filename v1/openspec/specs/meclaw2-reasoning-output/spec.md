# meclaw2-reasoning-output Specification

## Purpose
TBD - created by archiving change reasoning-panel-and-levels. Update Purpose after archive.
## Requirements
### Requirement: Bot-level reasoning configuration

The system SHALL allow each bot to configure reasoning behavior independently.

#### Scenario: Reasoning disabled by default

- **WHEN** a bot has no reasoning settings configured
- **THEN** reasoning SHALL be treated as off and provider payloads SHALL not request thinking output

#### Scenario: Reasoning level selection

- **WHEN** a bot has `reasoning_enabled` true and `reasoning_level` set to low, medium, or high
- **THEN** the system SHALL map that level to provider-specific reasoning parameters before calling the model

### Requirement: Separate reasoning stream from answer stream

The system SHALL deliver reasoning tokens separately from answer content tokens during chat generation.

#### Scenario: Reasoning token WebSocket event

- **WHEN** the provider streams reasoning content for an active generation
- **THEN** the server SHALL emit `reasoning_token` events distinct from `token` events

#### Scenario: Answer tokens unchanged

- **WHEN** the provider streams answer content
- **THEN** the server SHALL continue emitting `token` events containing answer text only

### Requirement: Reasoning persistence without context pollution

The system SHALL persist reasoning content on assistant messages without injecting it into subsequent model context or memory extraction.

#### Scenario: Message stores reasoning field

- **WHEN** generation completes with reasoning content
- **THEN** the assistant message SHALL include a `reasoning` field separate from `content`

#### Scenario: Next turn excludes reasoning

- **WHEN** building API messages for a follow-up user turn
- **THEN** the system SHALL include assistant `content` but SHALL NOT include prior `reasoning` text in the prompt

### Requirement: Reasoning UI panel

The chat UI SHALL display reasoning output when visible and enabled.

#### Scenario: Collapsible thinking panel

- **WHEN** `reasoning_visible` is true and reasoning tokens arrive
- **THEN** the UI SHALL show a collapsible panel above the answer showing streaming reasoning text

#### Scenario: Hidden reasoning

- **WHEN** `reasoning_visible` is false
- **THEN** the UI SHALL not render the thinking panel even if reasoning tokens are received

### Requirement: DeepSeek optimization integration

When a profile has the DeepSeek optimization enabled, the system SHALL control thinking via the DeepSeek thinking API instead of hard-disabling it whenever bot reasoning is enabled.

#### Scenario: DeepSeek thinking enabled

- **WHEN** bot reasoning is enabled and profile has DeepSeek optimization
- **THEN** the provider payload SHALL set thinking to enabled rather than forced disabled

#### Scenario: DeepSeek thinking disabled

- **WHEN** bot reasoning is off
- **THEN** the provider payload SHALL keep thinking disabled for DeepSeek profiles (preserving current default behavior)

