## ADDED Requirements

### Requirement: Editable file preview in code mode

When the user opens a file in programming mode, the system SHALL display file content in an editable text area instead of a read-only-only view, while preserving line-oriented display or equivalent editing experience.

#### Scenario: Open file for editing

- **WHEN** the user selects a file in the file tree within an active `working_dir`
- **THEN** the preview panel SHALL load file content into the editable area
- **AND** the panel SHALL indicate the file path in the header

#### Scenario: Read-only fallback for unsupported cases

- **WHEN** the file cannot be read as text or exceeds preview limits
- **THEN** the system SHALL show an error or truncated read-only message
- **AND** SHALL NOT allow save until valid text content is loaded

### Requirement: Word wrap editor setting

The application SHALL provide an editor preference for automatic word wrap, persisted in application config and applied to the code-mode editor view.

#### Scenario: Enable word wrap

- **WHEN** the user enables「自动换行」in editor settings and saves config
- **THEN** the code-mode editor SHALL wrap long lines without horizontal scrolling
- **AND** the preference SHALL persist after restart

#### Scenario: Disable word wrap

- **WHEN** the user disables automatic word wrap
- **THEN** the editor SHALL use horizontal scrolling or nowrap behavior for long lines

### Requirement: Save file within working directory

The user SHALL be able to save edits to disk only within the current programming mode `working_dir`.

#### Scenario: Successful save

- **WHEN** the user clicks Save or presses Ctrl+S with a dirty open file
- **THEN** the system SHALL write the editor buffer to the file path under `working_dir`
- **AND** SHALL mark the file as saved (no dirty indicator)

#### Scenario: Reject path outside working directory

- **WHEN** a save is attempted for a path that escapes `working_dir` after normalization
- **THEN** the system SHALL reject the operation with a clear error
- **AND** SHALL NOT write to disk

### Requirement: Dirty and saved status indicator

The preview header or toolbar SHALL show whether the current buffer differs from the last saved content on disk.

#### Scenario: Unsaved changes

- **WHEN** the user edits content after load or last save
- **THEN** the UI SHALL show an unsaved indicator (e.g. dot)

#### Scenario: Saved state

- **WHEN** save completes successfully
- **THEN** the UI SHALL show a saved indicator (e.g. checkmark)
- **AND** the dirty indicator SHALL be cleared

### Requirement: Editor keyboard shortcuts

The code-mode editor SHALL support basic keyboard shortcuts without autocomplete in this release.

#### Scenario: Save shortcut

- **WHEN** the user presses Ctrl+S while the editor is focused
- **THEN** the system SHALL trigger the same save action as the Save button

#### Scenario: New file shortcut

- **WHEN** the user presses Ctrl+N in programming mode with an active `working_dir`
- **THEN** the system SHALL prompt for a relative file name
- **AND** SHALL create or open a new editable buffer under `working_dir` after confirmation

### Requirement: Preserve existing preview actions

Copy and「发送给 AI分析」actions SHALL remain available alongside edit and save.

#### Scenario: Send to AI after edit

- **WHEN** the user clicks「发送给 AI分析」
- **THEN** the system SHALL use the current editor buffer content (including unsaved edits) for the AI handoff
