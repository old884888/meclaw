# mnemos-context-cache-discipline Specification

## Purpose
TBD - created by archiving change mnemos-prompt-cache-discipline. Update Purpose after archive.
## Requirements
### Requirement: Layered context assembly in multi-brain orchestrator

The multi-brain orchestrator SHALL assemble API messages in layers before dynamic per-turn content: **stable** (base system prompt, persona), **semi_stable** (reserved for project overview / group roster), and **dynamic** (memory retrieval, cognitive block, session summary, current time). Stable and semi_stable content MUST appear before conversation history; dynamic content MUST be placed at the tail.

#### Scenario: Stable layer excludes per-turn values

- **WHEN** the orchestrator builds API messages for a turn
- **THEN** the stable system content SHALL NOT contain query-derived memory retrieval results, cognitive blocks, session summaries, timestamps, or other per-turn values
- **AND** persona and base system prompt SHALL remain in the stable layer

#### Scenario: Dynamic blocks are appended at the tail

- **WHEN** memory retrieval, cognitive, session summary, or time blocks are produced for a turn
- **THEN** they SHALL be merged into a single dynamic context segment
- **AND** that segment SHALL be placed after conversation history, not as a system message preceding history

### Requirement: Dynamic context prefixes the last user message

The orchestrator SHALL inject the merged dynamic context segment by prefixing it onto the last user message content under a clear header, rather than emitting it as an early system message.

#### Scenario: Last user message exists

- **WHEN** the assembled messages contain at least one user message
- **THEN** the dynamic segment SHALL be prepended to the content of the last user message
- **AND** for multimodal content the segment SHALL be prepended to the first text part

#### Scenario: No user message present

- **WHEN** the assembled messages contain no user message
- **THEN** the system SHALL append a single user message containing only the dynamic context segment

### Requirement: Deterministic request payload serialization

Provider requests SHALL serialize the payload with a deterministic key order so that unchanged content yields byte-stable prefixes for server-side prompt caching.

#### Scenario: Payload key order is stable across requests

- **WHEN** two requests are built with identical content
- **THEN** the serialized request bodies SHALL be byte-identical for the stable prefix portion
- **AND** serialization SHALL use a deterministic key ordering

### Requirement: Cache usage is parsed from provider responses

When a provider response includes prompt cache usage fields, the system SHALL parse cache read and cache creation token counts and compute a hit rate. When the fields are absent, the system SHALL mark cache usage as unsupported without raising an error.

#### Scenario: Provider returns cache usage fields

- **WHEN** the response or stream usage includes `cache_read_input_tokens` / `prompt_cache_hit_tokens` and/or `cache_creation_input_tokens` / `prompt_cache_miss_tokens`
- **THEN** the system SHALL compute `hit_rate = read / (read + create) * 100`
- **AND** expose read, create, hit_rate, and supported=true for the turn

#### Scenario: Provider omits cache usage fields

- **WHEN** the response contains no recognizable cache usage fields
- **THEN** the system SHALL report cache usage as unsupported (supported=false)
- **AND** SHALL NOT raise an error or break the generation flow

### Requirement: Compression preserves the stable prefix

Context compaction SHALL only adjust conversation history and summary content; it MUST NOT rewrite the stable system prefix.

#### Scenario: Compaction runs on a long context

- **WHEN** the context exceeds a compaction threshold and compaction runs
- **THEN** the stable system prefix (base system + persona) SHALL remain unchanged
- **AND** only history and dynamic/summary content SHALL be altered

### Requirement: Reasoning mode cache trade-off disclosure

The system SHALL surface that enabling reasoning may reduce prefix cache hit rate compared to reasoning-off chat.

#### Scenario: Brain status notes reasoning cache impact

- **WHEN** a bot has reasoning enabled for a generation
- **THEN** brain status or settings UI SHALL indicate that reasoning mode may affect prompt cache efficiency

