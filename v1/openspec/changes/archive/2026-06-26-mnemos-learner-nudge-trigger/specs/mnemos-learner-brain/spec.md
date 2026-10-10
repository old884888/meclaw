## ADDED Requirements

### Requirement: Learner nudge trigger SHALL classify turn signals

The Learner brain SHALL classify completed turn signals and enqueue review jobs when configured nudge triggers match, without blocking the chat WebSocket response.

#### Scenario: User correction detected

- **WHEN** the user message indicates correction of a prior assistant answer
- **AND** `learner_nudge_enabled` is true
- **THEN** the Learner brain SHALL enqueue a review job for that turn
- **AND** the enqueue SHALL complete without delaying the `done` event

#### Scenario: Multi-turn revision on same task

- **WHEN** the same session revises a task across more than the configured turn threshold
- **THEN** the Learner brain SHALL enqueue a review job
- **AND** SHALL dedupe repeated nudges for the same topic within the configured window

#### Scenario: No trigger matched

- **WHEN** no nudge trigger matches
- **THEN** the Learner brain SHALL only persist the raw signal
- **AND** SHALL NOT enqueue a review job

### Requirement: Learner review SHALL produce pending candidates

Review jobs SHALL analyze bounded recent signals and write pending candidates without applying changes to soul, skills, or L3 automatically.

#### Scenario: Review job completes

- **WHEN** a review job runs successfully
- **THEN** it SHALL write one or more candidates with `status: pending`
- **AND** candidate types MAY include `l3_profile_update`, `skill_draft`, or `prompt_hint`
- **AND** `soul.md` SHALL NOT be modified

#### Scenario: Review job fails

- **WHEN** a review job errors
- **THEN** the failure SHALL be recorded
- **AND** chat behavior SHALL remain unaffected
