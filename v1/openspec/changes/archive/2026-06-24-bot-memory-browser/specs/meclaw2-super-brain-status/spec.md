## MODIFIED Requirements

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

#### Scenario: User opens memory browser from memory section

- **WHEN** the user clicks a memory layer count or memory browser entry control in the Memory section
- **THEN** the UI SHALL open the Bot memory browser for the current Bot
- **AND** preserve the current Bot and session context where applicable
