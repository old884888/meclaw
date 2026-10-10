## ADDED Requirements

### Requirement: Capacity-driven memory consolidation

The system SHALL run asynchronous consolidation jobs when configured memory capacity thresholds are exceeded, performing merge, compress, or archive actions without blocking chat.

#### Scenario: L3 profile exceeds capacity

- **WHEN** the L3 profile size exceeds its configured threshold
- **AND** `memory_consolidation_enabled` is true
- **THEN** the system SHALL enqueue a consolidation job to compress or merge profile content
- **AND** pinned constraints SHALL remain intact

#### Scenario: Topic chain exceeds length threshold

- **WHEN** a topic has more active L1 atoms than the configured chain limit
- **THEN** the system SHALL compress older atoms into a summary node or archive low-value atoms
- **AND** supersede relationships SHALL remain traceable

#### Scenario: Similar atoms merged

- **WHEN** two or more active L1 atoms in the same topic exceed embedding similarity threshold
- **AND** neither atom is pinned
- **THEN** the system SHALL merge them into a single representative atom
- **AND** SHALL record merge provenance for audit

#### Scenario: Archive low-value atoms

- **WHEN** an atom has low importance, low hit count, and age beyond recency half-life
- **AND** the atom is not pinned
- **THEN** the system SHALL mark it archived
- **AND** archived atoms SHALL NOT be injected by `before_chat` recall

#### Scenario: Consolidation is disabled

- **WHEN** `memory_consolidation_enabled` is false
- **THEN** no consolidation jobs SHALL run
- **AND** existing memory behavior SHALL be unchanged
