## ADDED Requirements

### Requirement: Bot launcher is the default home of MeClaw 2.0
The system SHALL render a Bot launcher grid as the first screen when the user opens `meclaw2/`.

#### Scenario: User opens the app
- **WHEN** the user loads the main 2.0 application shell
- **THEN** the first visible primary content SHALL be a grid of Bot modules
- **AND** each Bot module SHALL represent exactly one configured Bot
- **AND** the launcher SHALL NOT default to a session-first sidebar view

### Requirement: Launcher includes a fixed add tile
The launcher SHALL include a dedicated add-Bot tile that is visually part of the grid and fixed at the end of the list.

#### Scenario: Launcher renders with existing Bots
- **WHEN** the launcher renders one or more Bot modules
- **THEN** the final tile in the grid SHALL be a `+` tile for creating a new Bot
- **AND** the `+` tile SHALL remain after the last Bot regardless of Bot order changes

### Requirement: Bot modules provide direct entry and management actions
Each Bot module SHALL support entering the Bot workspace and expose edit and delete actions.

#### Scenario: User interacts with a Bot module
- **WHEN** the user views a Bot module on the launcher
- **THEN** the module SHALL expose an entry action for opening that Bot's chat workspace
- **AND** the module SHALL expose an edit action for opening the Bot editor
- **AND** the module SHALL expose a delete action for removing the Bot after confirmation

### Requirement: Launcher supports arrange mode with jiggle feedback
The launcher SHALL provide a dedicated arrange mode for Bot ordering.

#### Scenario: User enters arrange mode
- **WHEN** the user activates the launcher arrange control
- **THEN** all Bot modules SHALL enter a visible jiggle-style editing state
- **AND** Bot modules SHALL become draggable for reordering
- **AND** the `+` tile SHALL NOT become draggable

#### Scenario: User exits arrange mode after reordering
- **WHEN** the user finishes dragging Bot modules and exits arrange mode
- **THEN** the system SHALL persist the new Bot order
- **AND** a subsequent reload SHALL render Bots in the saved order

### Requirement: Launcher communicates Bot readiness
The launcher SHALL display whether a Bot is ready to chat based on its provider binding state.

#### Scenario: Bot has no bound provider
- **WHEN** a Bot has no valid provider binding or no usable provider configuration
- **THEN** its launcher module SHALL display a visible unconfigured state
- **AND** the launcher SHALL communicate that the Bot has no configured brain

### Requirement: Entering a Bot transitions into Bot-scoped chat
Selecting a Bot from the launcher SHALL open that Bot's workspace rather than silently changing only global selection state.

#### Scenario: User opens a Bot from the launcher
- **WHEN** the user activates a Bot module entry action
- **THEN** the UI SHALL navigate from the launcher into that Bot's chat workspace
- **AND** the workspace SHALL be scoped to the selected Bot
- **AND** the workspace SHALL provide a clear way to return to the launcher
