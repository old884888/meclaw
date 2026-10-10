## MODIFIED Requirements

### Requirement: L1 atomic memory extraction

The Memory brain SHALL extract atomic memories from completed turns. L1 records SHALL support quality metadata: `importance`, `hit_count`, `supersedes_id`, and `superseded_by` when applicable. When a preference switch is detected for a known `topic_key`, the system SHALL link the new atom to the prior current atom via `supersedes_id`.

#### Scenario: Preference switch supersedes prior atom

- **WHEN** a new L1 preference atom is written with `polarity` switch and a resolved `topic_key`
- **AND** a prior non-superseded atom exists for that topic
- **THEN** the new atom SHALL reference the prior atom in `supersedes_id`
- **AND** the prior atom SHALL record `superseded_by` pointing to the new atom

#### Scenario: Near-duplicate write is skipped

- **WHEN** embedding is available and `memory_dedupe_threshold` > 0
- **AND** a new atom body is semantically near-identical to a recent same-topic atom
- **THEN** the system SHALL skip creating a duplicate L1 file
- **AND** indexing SHALL remain consistent

### Requirement: before_chat recall is budgeted and layered

Hybrid recall SHALL apply a composite ranking score combining relevance, importance, recency decay, and hit-count boost. Atoms marked `superseded_by` SHALL be excluded from direct hit injection unless required for an explicit evolution-chain block.

#### Scenario: Superseded atoms filtered from hits

- **WHEN** hybrid search returns candidate atoms
- **AND** an atom has a non-empty `superseded_by` field
- **THEN** that atom SHALL NOT appear as a standalone hit snippet
- **AND** it MAY still appear inside a topic evolution chain when routed

#### Scenario: Recalled atoms gain hit count

- **WHEN** an L1 atom is injected into the memory block during `before_chat`
- **THEN** the system SHALL increment that atom's `hit_count` best-effort
- **AND** chat SHALL proceed if the increment fails
