## ADDED Requirements

### Requirement: Per-bot skill storage

The system SHALL store procedural skills per bot under the bot soul directory as human-readable files with structured frontmatter, separate from L1 atomic memory.

#### Scenario: Skill file is created on approval

- **WHEN** a pending `skill_draft` candidate is approved
- **THEN** the system SHALL write a skill file under the bot's skills directory
- **AND** SHALL index the skill for retrieval when status is `approved`

#### Scenario: Skill statuses

- **WHEN** a skill is pending, approved, archived, or superseded
- **THEN** only `approved` skills SHALL be eligible for recall injection
- **AND** superseded skills SHALL remain auditable but not injected

### Requirement: Progressive skill recall

The system SHALL retrieve and inject skills only when task intent is detected and relevance score exceeds threshold, within a configured token budget.

#### Scenario: Task intent triggers skill search

- **WHEN** the orchestrator detects task-oriented intent
- **AND** skill recall is enabled for the bot
- **THEN** the system SHALL search approved skills using hybrid embedding retrieval
- **AND** SHALL inject at most the configured top-k skills within `skill_token_budget`

#### Scenario: No relevant skill

- **WHEN** no approved skill exceeds the relevance threshold
- **THEN** no skill block SHALL be injected
- **AND** L1/L2 memory recall SHALL proceed unchanged

#### Scenario: Skill recall disabled

- **WHEN** skill recall is disabled for the bot or globally
- **THEN** the system SHALL NOT inject skill blocks
- **AND** skill files MAY still be stored for future use

### Requirement: Skill assets are not auto-applied

The system SHALL NOT automatically approve skill drafts or modify `soul.md` when skills are created or updated.

#### Scenario: Draft remains pending

- **WHEN** a review job produces a `skill_draft` candidate
- **THEN** the candidate SHALL remain `pending` until explicitly approved
- **AND** unapproved drafts SHALL NOT be injected into chat prompts
