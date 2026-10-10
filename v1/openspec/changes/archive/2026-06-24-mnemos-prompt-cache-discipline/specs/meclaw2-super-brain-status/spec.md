## MODIFIED Requirements

### Requirement: Composer shows session-level brain status

The chat composer SHALL show a lightweight status line for the current session, including cache hit rate when available.

#### Scenario: Session has no trace yet

- **WHEN** a session is selected but no `brain_trace` or `cache_usage` has been received
- **THEN** the composer status SHALL show message count and a neutral brain status
- **AND** the UI SHALL NOT display misleading recall, compression, or cache values

#### Scenario: Trace exists for current session

- **WHEN** a `brain_trace` event is received for the current session
- **THEN** the composer status SHALL show context ratio, compact tier, memory recall count if present, and background job state

#### Scenario: Cache usage is supported for current turn

- **WHEN** a `cache_usage` event with `supported = true` is received for the current session
- **THEN** the composer status SHALL show a cache hit rate such as `缓存命中 94%`

#### Scenario: Cache usage is unsupported

- **WHEN** a `cache_usage` event with `supported = false` is received, or no cache usage is available
- **THEN** the composer status SHALL omit the hit-rate value or show a neutral placeholder
- **AND** SHALL NOT show a misleading `0%`

### Requirement: Status detail panel explains current brain state

Clicking the topbar capsule SHALL open a read-only detail panel that includes cache usage in the Context section.

#### Scenario: User opens the status panel

- **WHEN** the user clicks the super brain status capsule
- **THEN** the panel SHALL display sections for Current Bot, Brains, Memory, Context, Background Jobs, and Turn Trace
- **AND** all sections SHALL tolerate missing data with clear empty states

#### Scenario: Context section shows cache metrics

- **WHEN** the latest turn reported cache usage with `supported = true`
- **THEN** the Context section SHALL show cache read tokens, cache creation tokens, and hit rate
- **AND** when cache usage is unsupported the section SHALL indicate the provider does not report cache metrics

### Requirement: WebSocket trace updates the status without full reload

The status UI SHALL consume WebSocket `brain_trace` and `cache_usage` events.

#### Scenario: Brain trace event arrives

- **WHEN** the WebSocket receives `event = "brain_trace"`
- **THEN** the frontend SHALL store the trace for the active session
- **AND** update the capsule, composer status, and detail panel if visible

#### Scenario: Cache usage event arrives

- **WHEN** the WebSocket receives `event = "cache_usage"` for the active session
- **THEN** the frontend SHALL store the cache metrics for that session
- **AND** update the composer status and the Context section of the detail panel if visible

#### Scenario: Trace event arrives for inactive session

- **WHEN** trace or cache data is associated with a session that is not currently selected
- **THEN** the frontend SHALL preserve it without overwriting the current session status
