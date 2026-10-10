## MODIFIED Requirements

### Requirement: Per-brain token budgets are enforced

Each activated brain SHALL have a hard token budget enforced before the API call. Budget values SHALL be resolved from bot-level overrides first, then global defaults.

#### Scenario: Bot overrides persona budget

- **WHEN** a bot sets `brains.persona_token_budget`
- **THEN** the Persona brain SHALL use the bot-specific budget
- **AND** other bots without overrides SHALL continue using global `persona_token_budget`

#### Scenario: Memory recall exceeds budget

- **WHEN** recalled memory snippets exceed the effective `memory_token_budget`
- **THEN** the orchestrator SHALL truncate from lowest priority items first
- **AND** the API call SHALL still proceed without error

#### Scenario: Brain trace is available in debug mode

- **WHEN** `brain_trace_enabled` is true
- **THEN** the server MAY emit a `brain_trace` event listing activated brains and estimated token usage per block
- **AND** default configuration SHALL keep `brain_trace_enabled` false
