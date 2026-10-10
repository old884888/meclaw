## MODIFIED Requirements

### Requirement: Tier 3 summarize uses incremental running summary

When context pressure reaches tier 3, the compaction engine SHALL produce or update a running session summary with a single LLM call using the bot's resolved background model.

#### Scenario: Tier 3 compaction triggers

- **WHEN** estimated ratio reaches `compaction_tier3_pct`
- **THEN** the engine SHALL generate an incremental summary from delta messages since the last summary
- **AND** API messages SHALL be rebuilt to include the summary plus protected recent messages
- **AND** the summarization LLM call SHALL use `background_model` when configured
