# mnemos-learner-brain Specification

## Purpose

Offline learner brain for MNEMOS: collect signals, produce pending candidates, never block real-time chat.

## Requirements

### Requirement: Learner brain runs offline only

The Learner brain SHALL NOT participate in real-time prompt assembly or streaming generation.

#### Scenario: User sends a chat message

- **WHEN** a turn is processed
- **THEN** the Learner brain SHALL NOT add tokens to the API messages for that turn
- **AND** learner work SHALL be limited to signal collection or queued jobs

### Requirement: Learner collects turn signals asynchronously

After each completed turn, the system MAY enqueue learner signals without blocking the WebSocket response.

#### Scenario: Turn completes with learner enabled

- **WHEN** `learner_enabled` is true and assistant generation completes
- **THEN** the Learner brain SHALL record a turn signal with session id, bot id, and bounded turn metadata
- **AND** signal collection SHALL complete without delaying the `done` event

### Requirement: Learner produces candidates rather than auto-applying changes

The Learner brain SHALL write proposed profile or prompt updates as pending candidates.

#### Scenario: Scheduled learner job optimizes user profile text

- **WHEN** the scheduled learner task runs
- **THEN** it MAY generate candidate L3 profile updates or prompt suggestions
- **AND** candidates SHALL remain inactive until explicitly approved
- **AND** `soul.md` SHALL NOT be overwritten automatically

### Requirement: Learner schedule is configurable

The system SHALL support a configurable schedule for learner batch processing.

#### Scenario: Default configuration is loaded

- **WHEN** a fresh data directory is initialized
- **THEN** `learner_enabled` and `learner_schedule` SHALL be present in config
- **AND** learner batch work MAY be disabled by default in early phases

### Requirement: Learner feedback analysis is bounded

Learner batch jobs SHALL analyze only a bounded recent window of signals or feedback.

#### Scenario: Nightly learner job runs

- **WHEN** the learner scheduler triggers
- **THEN** analysis SHALL be limited to configured recent days or signal count
- **AND** the job SHALL be safe to skip when no new signals exist

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
