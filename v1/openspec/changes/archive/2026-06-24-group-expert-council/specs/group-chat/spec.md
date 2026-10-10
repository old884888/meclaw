## ADDED Requirements

### Requirement: Group run modes

A group session SHALL support two run modes: free-chat (existing @-mention reply chain) and expert-council. The two modes SHALL be mutually exclusive within a single user turn.

#### Scenario: Free-chat is the default mode

- **WHEN** the user sends a group message without enabling council mode
- **THEN** the session SHALL behave as the existing free-chat mode
- **AND** @-mention reply rules SHALL apply unchanged

#### Scenario: Council mode supersedes free-chat for that turn

- **WHEN** the user sends a topic with council mode enabled
- **THEN** the system SHALL run the council pipeline for that turn
- **AND** SHALL NOT additionally trigger the probabilistic free-chat reply chain for the same turn

#### Scenario: Council outputs stored in session history

- **WHEN** a council run produces round outputs and a recommendation
- **THEN** those messages SHALL be stored in the group session history with their speaker Bot identity
- **AND** SHALL be re-renderable when the session is reopened
