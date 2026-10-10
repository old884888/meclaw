## MODIFIED Requirements

### Requirement: L1 atomic memory extraction

The Memory brain SHALL extract atomic memories from completed turns. When structured LLM extraction is enabled, the system SHALL parse a validated JSON schema into L1 records typed as fact, preference, constraint, or todo, including optional structured fields (`subject`, `predicate`, `object`, `polarity`, `confidence`, `topic_key`, `reason`, `supersedes_hint`). When LLM extraction is unavailable or fails, the system SHALL fall back to heuristic extraction without blocking the turn.

#### Scenario: L1 extraction runs after a turn

- **WHEN** `l1_extract_every_turn` is true or the turn is queued for batch extraction
- **THEN** the system SHALL create or update L1 records typed as fact, preference, constraint, or todo
- **AND** each L1 record SHALL reference its source turn or L0 evidence id

#### Scenario: Structured LLM extraction succeeds

- **WHEN** `l1_extract_mode` is `llm` or `hybrid`
- **AND** the extraction role model is configured
- **AND** the LLM returns valid structured JSON
- **THEN** the system SHALL map each JSON atom into L1 frontmatter and index fields
- **AND** `supersedes_hint` SHALL link to prior atoms on the same topic when resolvable

#### Scenario: Structured LLM extraction fails

- **WHEN** the LLM returns invalid JSON, times out, or errors
- **THEN** the system SHALL fall back to heuristic extraction for that turn
- **AND** chat completion SHALL NOT be blocked

#### Scenario: Extraction respects atom budget

- **WHEN** structured extraction produces more atoms than the configured per-turn limit
- **THEN** the system SHALL keep the highest-confidence atoms up to the limit
- **AND** SHALL log or trace that truncation occurred
