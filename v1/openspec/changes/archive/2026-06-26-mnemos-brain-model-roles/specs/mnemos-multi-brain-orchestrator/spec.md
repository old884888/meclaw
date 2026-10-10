## MODIFIED Requirements

### Requirement: Async hooks do not block WebSocket completion

Post-turn memory and learner work SHALL run asynchronously after the assistant response is persisted. Background tasks (L1 extraction, Tier3 summary) SHALL obtain their model via the per-role resolver (`extraction`, `summary`) rather than a fixed background/executor split, while preserving the existing fallback behavior when roles are unconfigured.

#### Scenario: Assistant generation completes

- **WHEN** the WebSocket emits `done` or `stopped`
- **THEN** `after_turn` and learner signal collection SHALL be scheduled asynchronously
- **AND** the client SHALL NOT wait for L1 extraction or learner processing to receive the final event

#### Scenario: Background task resolves its model by role

- **WHEN** an asynchronous extraction or summary task runs
- **THEN** it SHALL resolve its model through the per-role resolver for `extraction` or `summary`
- **AND** when that role is unconfigured it SHALL fall back to the background model, then the executor model

#### Scenario: Role resolution unavailable

- **WHEN** no usable model can be resolved for a background role
- **THEN** the task SHALL skip or degrade without blocking chat
- **AND** the failure SHALL be recorded in job status rather than raised to the user
