## ADDED Requirements

### Requirement: Summary detail levels for context compression

The system SHALL support four summary detail levels for context compression, exposed in the UI as **摘要详略**: 极简 (`minimal`), 标准 (`standard`), 详尽 (`detailed`), and 琐碎 max (`max`). The selected level SHALL control the conversation-summary prompt template only and SHALL NOT by itself change memory item length limits except where explicitly specified for `max` memory enhancement.

#### Scenario: Standard is default

- **WHEN** the user compresses context without specifying a detail level
- **THEN** the system SHALL use `standard` detail level
- **AND** the resulting summary behavior SHALL match pre-change default compression

#### Scenario: Minimal produces shortest summary

- **WHEN** the user selects 极简 and confirms compression
- **THEN** the summary prompt SHALL instruct the model to output a minimal bullet list
- **AND** SHALL omit extended structure and verbatim quotes

#### Scenario: Detailed produces structured summary

- **WHEN** the user selects 详尽 and confirms compression
- **THEN** the summary prompt SHALL instruct structured sections (e.g. background, key points, conclusions, open items)
- **AND** SHALL preserve more decision detail than `standard`

#### Scenario: Max preserves granular points and selective quotes

- **WHEN** the user selects 琐碎 max and confirms compression
- **THEN** the summary prompt SHALL allow multi-topic bullet lists and limited verbatim quote excerpts
- **AND** SHALL NOT paste full conversation logs into the summary
- **AND** the UI SHALL warn that context usage may increase

### Requirement: Compression direction stacks with detail level

The optional user-provided compression direction (free text) SHALL be appended to the detail-level template when building the summary prompt.

#### Scenario: User provides direction with detailed level

- **WHEN** the user selects 详尽 and enters a compression direction
- **THEN** the system SHALL apply the detailed template AND include the user's direction as additional constraints

### Requirement: Detail level configuration and resolution

The application SHALL store a global default `compress_summary_detail` (default `standard`) and MAY allow per-bot override. Manual compression SHALL use the level chosen in the compress dialog. Automatic compression SHALL use the resolved default without showing the dialog.

#### Scenario: Bot overrides global default

- **WHEN** global default is `standard` and active bot sets `compress_summary_detail` to `detailed`
- **THEN** automatic compression for that bot SHALL use `detailed`

#### Scenario: Manual compress uses dialog selection

- **WHEN** the user selects 琐碎 max in the compress dialog and confirms
- **THEN** that compress operation SHALL use `max` regardless of global default

### Requirement: compress_context accepts detail level

The backend API `compress_context` SHALL accept an optional `detail_level` parameter with values `minimal`, `standard`, `detailed`, or `max`.

#### Scenario: Invalid detail level rejected

- **WHEN** `compress_context` is called with an unknown detail level
- **THEN** the system SHALL fall back to `standard`
