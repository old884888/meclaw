# mnemos-context-compaction Specification

## Purpose

Tiered context compaction for long MNEMOS conversations: snip, prune with monotonic cache, and incremental LLM summaries.

## Requirements

### Requirement: Context pressure is measured before each API call

The Memory brain SHALL measure context pressure as a ratio of estimated prompt tokens to the active model context limit.

#### Scenario: Context is below tier 1 threshold

- **WHEN** estimated ratio is below `compaction_tier1_pct`
- **THEN** no compaction SHALL run
- **AND** no extra LLM summarization call SHALL be made for compaction

### Requirement: Tier 1 snip reduces bulky content without LLM cost

When context pressure reaches tier 1, the compaction engine SHALL snip oversized tool outputs and long code blocks.

#### Scenario: Tool output exceeds snip threshold

- **WHEN** tier 1 compaction runs on a tool or long text message
- **THEN** the engine SHALL keep a short leading excerpt and an omission marker
- **AND** full content SHALL be offloaded to session-scoped storage when available

### Requirement: Tier 2 prune uses monotonic replacement cache

When context pressure reaches tier 2, the compaction engine SHALL replace eligible messages with cached decisions.

#### Scenario: Message part was previously pruned in the session

- **WHEN** tier 2 compaction encounters a part with an existing replacement decision
- **THEN** the engine SHALL reuse the cached decision without re-evaluating content
- **AND** previously replaced content SHALL NOT be restored in later turns

#### Scenario: First-time prune decision

- **WHEN** a compressible part has no cached decision
- **THEN** the engine SHALL create a replacement decision, persist it, and apply the replacement

### Requirement: Tier 3 summarize uses incremental running summary

When context pressure reaches tier 3, the compaction engine SHALL produce or update a running session summary with a single LLM call.

#### Scenario: Tier 3 compaction triggers

- **WHEN** estimated ratio reaches `compaction_tier3_pct`
- **THEN** the engine SHALL generate an incremental summary from delta messages since the last summary
- **AND** API messages SHALL be rebuilt to include the summary plus protected recent messages

### Requirement: Protection zone preserves recent context

Compaction SHALL NOT modify messages inside the protection zone.

#### Scenario: Recent messages fall within protection zone

- **WHEN** compaction runs
- **THEN** the most recent messages within `protection_zone_tokens` SHALL remain unchanged
- **AND** only older compressible messages SHALL be snipped, pruned, or summarized

### Requirement: Compaction blocks generation until complete

Compaction required for the current pressure tier SHALL complete before the main LLM stream starts.

#### Scenario: Tier 2 compaction is required

- **WHEN** context pressure requires tier 2 processing
- **THEN** compaction SHALL finish before `stream_chat` begins
- **AND** the user SHALL NOT receive model tokens until compaction completes or fails gracefully

#### Scenario: Compaction fails

- **WHEN** compaction fails unexpectedly
- **THEN** the system SHALL fall back to the best-effort pre-compaction messages or return a clear error
- **AND** the session history file SHALL remain uncorrupted
