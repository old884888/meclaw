## MODIFIED Requirements

### Requirement: L1 atomic memory extraction

The Memory brain SHALL extract atomic memories from completed turns. Each L1 record SHALL include normalized topic metadata to support preference evolution tracking: `topic_key`, `polarity` (`positive`, `negative`, or `switch`), monotonic `seq`, and optional `reason` when the source message states a change rationale.

#### Scenario: L1 extraction runs after a turn

- **WHEN** `l1_extract_every_turn` is true or the turn is queued for batch extraction
- **THEN** the system SHALL create or update L1 records typed as fact, preference, constraint, or todo
- **AND** each L1 record SHALL reference its source turn or L0 evidence id
- **AND** each L1 record SHALL include `topic_key` and `seq` metadata when extractable

#### Scenario: Switch polarity detected

- **WHEN** a user message indicates a preference change (e.g. 改成, 不再, switched to, used to)
- **THEN** the extracted L1 record SHALL set `polarity` to `switch`
- **AND** the record SHOULD capture a `reason` fragment when a because/since clause is present

#### Scenario: Legacy L1 records without topic metadata

- **WHEN** an existing L1 record lacks `topic_key` or `seq`
- **THEN** the system SHALL remain able to read and index the record
- **AND** aggregation and recall SHALL derive fallback ordering from `created_at` or file mtime

### Requirement: L3 user profile is a compressed long-term persona input

The Memory brain SHALL maintain an L3 user profile used by the Persona brain and/or Memory brain as a short injected summary. The profile SHALL be generated from bot-scoped L1 atomic memories and L2 summaries, stored separately from `soul.md`, and bounded before injection.

#### Scenario: Profile exists for a bot scope

- **WHEN** `before_chat` runs
- **THEN** the Persona brain SHALL receive a bounded excerpt derived from L3
- **AND** the excerpt SHALL NOT exceed `persona_token_budget`

#### Scenario: Profile is missing but memory exists

- **WHEN** L1 or L2 memory exists for a bot
- **AND** no L3 profile exists
- **THEN** the Memory brain SHALL be able to generate an initial L3 profile from existing memory records
- **AND** chat SHALL still proceed if generation is skipped or fails

#### Scenario: Profile is refreshed

- **WHEN** the configured L3 update interval is reached or a manual refresh is requested
- **THEN** the Memory brain SHALL update the L3 profile from current L1/L2 memory
- **AND** the profile SHALL include last-updated metadata or equivalent traceability

#### Scenario: Preference evolves

- **WHEN** newer L1 memories conflict with older preferences for the same `topic_key`
- **THEN** the L3 profile SHALL render an ordered evolution timeline for that topic showing historical steps, change reasons when available, and an explicit current value
- **AND** older evidence SHALL remain traceable in L1/L0 rather than being deleted automatically

#### Scenario: Soul remains human-authored

- **WHEN** L3 profile is generated or refreshed
- **THEN** `soul.md` SHALL NOT be modified automatically
- **AND** generated profile content SHALL remain under the bot memory directory

### Requirement: before_chat recall is budgeted and layered

The Memory brain `before_chat` hook SHALL return only budgeted, high-priority memory for the current query. Recall SHALL use the configured retrieval strategy: `fts` for exact SQLite FTS matching, or `hybrid` for local FTS plus lightweight semantic/lexical ranking suitable for personalized questions. When relevant L1 or L2 memory exists within budget, `before_chat` SHALL return a non-empty memory block with traceable snippets instead of silently falling back to no recall.

#### Scenario: Default recall on a new message

- **WHEN** `memory_retrieval_enabled` is true
- **THEN** recall SHALL prioritize current session L2 summary, then L1 top-k matches, then optional cross-session L2 when routed
- **AND** recall SHALL NOT inject entire L0 archives by default

#### Scenario: Hybrid recall handles semantic personalization

- **WHEN** `memory_retrieval_strategy` is `hybrid`
- **AND** a user asks a personalization-sensitive question that does not share exact keywords with stored L1 preferences
- **THEN** the Memory brain SHALL use local hybrid ranking and query expansion to retrieve relevant L1 or L2 memories
- **AND** the returned memory block SHALL include at least one relevant snippet when such memory exists within `memory_token_budget`

#### Scenario: FTS strategy remains available

- **WHEN** `memory_retrieval_strategy` is `fts`
- **THEN** the Memory brain SHALL use SQLite FTS recall behavior
- **AND** the system SHALL still proceed when no FTS match is found

#### Scenario: Memory budget is enforced

- **WHEN** hybrid recall returns more candidate memories than fit in `memory_token_budget`
- **THEN** the Memory brain SHALL include the highest-ranked snippets first
- **AND** lower-ranked snippets SHALL be omitted rather than exceeding the budget

#### Scenario: Topic-chain recall for evolution questions

- **WHEN** recall matches an L1 atom that has a `topic_key`
- **AND** multiple L1 atoms share that `topic_key`
- **THEN** the Memory brain SHALL include the ordered evolution chain for that topic in the memory block
- **AND** the chain SHALL be sorted by `seq` (or fallback timestamp) ascending before injection
