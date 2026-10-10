## ADDED Requirements

### Requirement: Composer toolbar layout

The chat input area SHALL present a two-row composer: an upper control toolbar and a lower row containing attachment control, message input, send, and stop buttons.

#### Scenario: Default chat mode layout

- **WHEN** the user is in chat mode and the input area is visible
- **THEN** the composer toolbar appears above the message input row
- **AND** the attachment and send controls remain on the input row

#### Scenario: Code mode new-task placement

- **WHEN** the user is in code mode
- **THEN** the existing「新任务」control MAY appear on the same toolbar row or immediately above the input row without duplicating send controls

### Requirement: DeepSeek reply mode quick toggle

When the active bot's API profile provider is `deepseek`, the composer toolbar SHALL expose「快速」and「思考」mode toggles that map to the active bot's `thinking_enabled` field.

#### Scenario: Switch to thinking mode

- **WHEN** the user selects「思考」on the composer toolbar for a DeepSeek bot
- **THEN** the system SHALL persist `thinking_enabled: true` on the active bot
- **AND** the header mode badge and status panel reply-mode text SHALL reflect thinking mode on next UI refresh

#### Scenario: Switch to fast mode

- **WHEN** the user selects「快速」on the composer toolbar for a DeepSeek bot
- **THEN** the system SHALL persist `thinking_enabled: false` on the active bot

#### Scenario: Non-DeepSeek bot hides mode toggles

- **WHEN** the active bot's profile provider is not `deepseek`
- **THEN** the composer toolbar SHALL NOT show fast/thinking mode toggles or depth controls

### Requirement: Thinking depth control

When thinking mode is enabled for a DeepSeek bot, the composer toolbar SHALL expose depth selection for `high` and `max` values stored on the active bot's `thinking_depth` field.

#### Scenario: Select depth max

- **WHEN** thinking mode is active and the user selects「加深 max」
- **THEN** the system SHALL persist `thinking_depth: max` on the active bot

#### Scenario: Depth hidden in fast mode

- **WHEN** fast mode is active
- **THEN** depth controls SHALL be hidden or disabled

### Requirement: Skills quick access

The composer toolbar SHALL provide a skills control that reflects enabled skills for the active bot and allows changing skill enablement without opening the full settings modal for the common case.

#### Scenario: Global skills bot

- **WHEN** the active bot has `skills_use_global` true (or not false)
- **THEN** the skills control SHALL indicate how many global skills are enabled
- **AND** opening the popover SHALL list all scanned skills with checkboxes bound to `config.enabled_skills`
- **AND** saving toggles SHALL persist global enabled skills via existing config save path

#### Scenario: Custom skills bot

- **WHEN** the active bot has `skills_use_global` false
- **THEN** the skills popover SHALL indicate custom mode
- **AND** SHALL allow editing that bot's `enabled_skills` list OR provide a clear action to open bot edit for skills

### Requirement: Toolbar state synchronization

The composer toolbar SHALL initialize from cached config when the app loads, when the active bot changes, and after bot or config save operations complete.

#### Scenario: Switch active bot

- **WHEN** the user switches to another bot from the bot selector
- **THEN** the toolbar mode, depth, and skills summary SHALL update to match the newly active bot and its profile provider
