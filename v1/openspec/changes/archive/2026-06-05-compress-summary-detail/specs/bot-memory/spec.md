## MODIFIED Requirements

### Requirement: Dual pipeline on context compression

When the user triggers context compression (`compress_context`), the system SHALL run two jobs: (1) conversation summary for the current session using the resolved **摘要详略** detail level (`minimal`, `standard`, `detailed`, or `max`), and (2) memory extraction when `memory_enabled` is true and write is not read-only, producing structured candidates written to `memory/items/`, index updates, and optional `memory.md` merge.

#### Scenario: Manual compress with memory on

- **WHEN** the user compresses context with memory enabled and not read-only
- **THEN** the system SHALL update `current_summary` using the selected or resolved detail level
- **AND** SHALL run memory extraction on the compressed segment
- **AND** SHALL write approved items to category folders and update the index
- **AND** SHALL merge elite facts into `memory.md` when applicable
- **AND** SHALL NOT write memory during streaming assistant output

#### Scenario: Low-quality candidate filtered

- **WHEN** extraction returns vague or session-ephemeral content (e.g. "user asked a question today")
- **THEN** the curator SHALL reject or mark `action: ignore`
- **AND** SHALL NOT persist such items

## ADDED Requirements

### Requirement: Optional quote extraction on max detail compression

When context compression runs with detail level `max` and memory write is enabled, the memory extraction step MAY extract up to three additional `quote` type items from the compressed segment, subject to the same quality filters and deduplication rules as other memory items.

#### Scenario: Max compress with memorable phrases

- **WHEN** the user compresses with detail level `max` and memory write enabled
- **AND** the conversation contains clearly reusable phrasing
- **THEN** the system MAY persist up to three `quote` items under `memory/items/quote/`
- **AND** SHALL still reject low-quality or duplicate quotes

#### Scenario: Non-max compress does not auto-quote

- **WHEN** the user compresses with detail level `standard` or `detailed`
- **THEN** automatic quote extraction SHALL NOT run beyond existing extraction rules
- **AND** users MAY still manually collect quotes via the message action button
