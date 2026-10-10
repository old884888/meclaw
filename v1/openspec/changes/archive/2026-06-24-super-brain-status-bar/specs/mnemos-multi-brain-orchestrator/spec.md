## MODIFIED Requirements

### Requirement: Per-brain token budgets are enforced

Each activated brain SHALL have a hard token budget enforced before the API call. The orchestrator SHALL expose enough structured trace data for the super brain status UI to explain budget usage.

#### Scenario: Memory recall exceeds budget

- **WHEN** recalled memory snippets exceed `memory_token_budget`
- **THEN** the orchestrator SHALL truncate from lowest priority items first
- **AND** the API call SHALL still proceed without error

#### Scenario: Brain trace is available in debug mode

- **WHEN** `brain_trace_enabled` is true
- **THEN** the server MAY emit a `brain_trace` event listing activated brains and estimated token usage per block
- **AND** default configuration SHALL keep `brain_trace_enabled` false

#### Scenario: Status UI consumes latest trace

- **WHEN** the orchestrator prepares a turn
- **THEN** the trace object SHALL include stable keys for `activated`, `tokens`, `compact_tier`, and `context_ratio`
- **AND** missing optional sections SHALL default to empty objects or arrays instead of breaking UI rendering

### Requirement: Multi-brain trace describes routing and memory decisions

The orchestrator trace SHALL include machine-readable details needed by the status bar.

#### Scenario: Memory brain is activated

- **WHEN** the Memory brain contributes a prompt block
- **THEN** trace SHALL indicate memory activation
- **AND** SHOULD include recall count, cross-session recall flag, and L0 deep recall flag when available

#### Scenario: Cognitive brain is not activated

- **WHEN** the Cognitive brain is enabled but routing does not activate it
- **THEN** trace SHALL allow the UI to represent it as enabled but inactive
- **AND** no cognitive token usage SHALL be reported above zero

#### Scenario: Context compaction runs

- **WHEN** compaction changes the message list or reaches a configured tier
- **THEN** trace SHALL include the resulting `compact_tier`
- **AND** SHALL include a context ratio rounded for display

### Requirement: Brain status API can summarize orchestrator state

The backend SHALL provide a Bot-scoped status summary using current configuration and latest known trace.

#### Scenario: No turn has run yet

- **WHEN** status is requested before any trace exists
- **THEN** the status response SHALL still include enabled/disabled states derived from effective configuration
- **AND** active states SHALL default to false except Executor when chat-ready

#### Scenario: Latest trace exists

- **WHEN** status is requested after a trace exists for the session
- **THEN** the response SHALL merge trace activation and token usage into the brain sections
