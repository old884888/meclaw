# mnemos-multi-brain-orchestrator Specification

## Purpose

Multi-brain orchestration for MNEMOS personal chat: rule-based routing, token budgets, and cache-friendly prompt assembly before each LLM call.
## Requirements
### Requirement: Multi-brain orchestrator is the chat assembly entry point

When `multi_brain_enabled` is true, the server SHALL route each user turn through a Multi-Brain Orchestrator before calling the LLM.

#### Scenario: User sends a message in an enabled session

- **WHEN** the WebSocket receives a valid `send` event
- **THEN** the server SHALL invoke the orchestrator to build API messages
- **AND** the orchestrator SHALL NOT require the LLM to decide which brains to activate

#### Scenario: Multi-brain disabled

- **WHEN** `multi_brain_enabled` is false
- **THEN** chat SHALL fall back to the existing `system + history` assembly
- **AND** no brain-specific storage SHALL be required for a successful reply

### Requirement: Executor brain is the only outward-facing brain

The Executor brain SHALL be responsible for session loading, orchestrator invocation, LLM streaming, and assistant message persistence.

#### Scenario: Turn completes successfully

- **WHEN** generation finishes with status `done` or `stopped`
- **THEN** the assistant message SHALL be saved through the existing history store
- **AND** the Executor SHALL NOT write L0/L1/L2/L3 records directly

### Requirement: Deterministic intent router selects optional brains

The system SHALL use a rule-based intent router with zero LLM cost to decide whether optional brains activate for a turn.

#### Scenario: Default personal chat message

- **WHEN** the user message does not match cross-session or cognitive intent rules
- **THEN** only Executor, Persona, and Memory brains SHALL contribute prompt blocks
- **AND** Cognitive brain token usage SHALL be zero

#### Scenario: Cross-session continuation intent

- **WHEN** the user message matches continuation patterns such as references to prior conversations
- **THEN** the router SHALL enable cross-session recall in the Memory brain
- **AND** recall SHALL remain within configured token budgets

#### Scenario: Planning or implementation intent

- **WHEN** the user message matches cognitive intent patterns
- **THEN** the Cognitive brain SHALL contribute a bounded structured block
- **AND** total cognitive injection SHALL NOT exceed `cognitive_token_budget`

### Requirement: Prompt assembly order is stable and cache-friendly

The orchestrator SHALL assemble messages in a stable order to support prompt caching discipline. When skill recall is enabled and task intent is detected, approved skill content MAY be injected as a dynamic block without modifying the stable system prefix.

#### Scenario: Messages are built for API call

- **WHEN** the orchestrator produces API messages
- **THEN** the order SHALL be: base system (soul) → persona block → memory block → optional skill block → optional cognitive block → session summary → conversation history → current user input
- **AND** each optional block SHALL be omitted entirely when its budget is zero or brain is inactive
- **AND** skill blocks SHALL include only approved skills within `skill_token_budget`

### Requirement: Per-brain token budgets are enforced

Each activated brain SHALL have a hard token budget enforced before the API call.

#### Scenario: Memory recall exceeds budget

- **WHEN** recalled memory snippets exceed `memory_token_budget`
- **THEN** the orchestrator SHALL truncate from lowest priority items first
- **AND** the API call SHALL still proceed without error

#### Scenario: Brain trace is available in debug mode

- **WHEN** `brain_trace_enabled` is true
- **THEN** the server MAY emit a `brain_trace` event listing activated brains and estimated token usage per block
- **AND** default configuration SHALL keep `brain_trace_enabled` false

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

