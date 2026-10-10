## ADDED Requirements

### Requirement: Topbar exposes a super brain status capsule

MNEMOS SHALL expose a compact super brain status capsule in the topbar when the web app is loaded.

#### Scenario: User is on the Bot launcher

- **WHEN** no Bot workspace is selected
- **THEN** the capsule SHALL show an idle state such as `大脑空闲`
- **AND** clicking the capsule SHALL open the status detail panel with an empty-state explanation

#### Scenario: User enters a chat-ready Bot

- **WHEN** a Bot with valid provider and model is selected
- **THEN** the capsule SHALL show overall health, memory summary, and context ratio when available
- **AND** the capsule SHALL use a non-error visual state

#### Scenario: Selected Bot is not chat-ready

- **WHEN** the current Bot lacks provider, API key, URL, or model
- **THEN** the capsule SHALL show an error or warning state
- **AND** the detail panel SHALL include the Bot readiness message

### Requirement: Composer shows session-level brain status

The chat composer SHALL show a lightweight status line for the current session.

#### Scenario: Session has no trace yet

- **WHEN** a session is selected but no `brain_trace` has been received
- **THEN** the composer status SHALL show message count and a neutral brain status
- **AND** the UI SHALL NOT display misleading recall or compression values

#### Scenario: Trace exists for current session

- **WHEN** a `brain_trace` event is received for the current session
- **THEN** the composer status SHALL show context ratio, compact tier, memory recall count if present, and background job state

### Requirement: Status detail panel explains current brain state

Clicking the topbar capsule SHALL open a read-only detail panel.

#### Scenario: User opens the status panel

- **WHEN** the user clicks the super brain status capsule
- **THEN** the panel SHALL display sections for Current Bot, Brains, Memory, Context, Background Jobs, and Turn Trace
- **AND** all sections SHALL tolerate missing data with clear empty states

#### Scenario: Brain statuses are rendered

- **WHEN** status data includes enabled and active fields for brain components
- **THEN** the UI SHALL render executor, persona, memory, cognitive, and learner states distinctly
- **AND** disabled, inactive, active, warning, and error states SHALL be visually distinguishable

### Requirement: Brain status loads from a single API

The frontend SHALL load super brain status from a single Bot-scoped endpoint.

#### Scenario: Frontend requests status

- **WHEN** the current Bot changes, session changes, settings are saved, or generation completes
- **THEN** the frontend SHALL call `/api/bots/{bot_id}/brain/status`
- **AND** it MAY pass `session_id` when a session is selected

#### Scenario: Status API fails

- **WHEN** the status API request fails
- **THEN** the capsule SHALL show a warning or error state
- **AND** chat SHALL remain usable

### Requirement: WebSocket trace updates the status without full reload

The status UI SHALL consume WebSocket `brain_trace` events.

#### Scenario: Brain trace event arrives

- **WHEN** the WebSocket receives `event = "brain_trace"`
- **THEN** the frontend SHALL store the trace for the active session
- **AND** update the capsule, composer status, and detail panel if visible

#### Scenario: Trace event arrives for inactive session

- **WHEN** trace data is associated with a session that is not currently selected
- **THEN** the frontend SHALL preserve it without overwriting the current session status

### Requirement: Status UI is read-only

The super brain status UI SHALL not change Bot configuration or memory records.

#### Scenario: User opens and closes status panel

- **WHEN** the user interacts with the status capsule and detail panel
- **THEN** no config, history, or memory files SHALL be modified
- **AND** configuration changes SHALL remain in Bot editor and Settings only
