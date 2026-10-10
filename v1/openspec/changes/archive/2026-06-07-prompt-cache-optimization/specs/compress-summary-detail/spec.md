## ADDED Requirements

### Requirement: Cache-safe summary injection after compression

After context compression, the session summary (`current_summary`) SHALL be injected according to `context-cache-discipline` as dynamic context. Compression MUST NOT rewrite stable system prompts, tool definitions, or prior conversation message content to reduce tokens.

#### Scenario: Summary placed in dynamic layer

- **WHEN** a session has a non-empty `current_summary` and the user sends a new message
- **THEN** the summary SHALL be injected in the dynamic context layer after stable and semi_stable blocks
- **AND** SHALL NOT be prepended into the stable system prompt

#### Scenario: Compress does not mutate stable prefix

- **WHEN** the user triggers `compress_context`
- **THEN** the system SHALL update `current_summary` and trim stored messages as today
- **AND** SHALL NOT modify bot soul content, fixed skill instructions, or tool definitions as part of compression
- **AND** SHALL NOT edit content of retained historical messages except removing truncated tail messages

#### Scenario: Auto compress remains cache-safe

- **WHEN** automatic compression triggers at the configured threshold
- **THEN** the resulting summary SHALL follow the same dynamic-layer injection rules as manual compression
- **AND** SHALL NOT introduce per-turn timestamps into the stable system prompt
