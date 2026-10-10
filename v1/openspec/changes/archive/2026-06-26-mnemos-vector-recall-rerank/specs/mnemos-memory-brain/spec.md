## MODIFIED Requirements

### Requirement: before_chat recall is budgeted and layered

The Memory brain `before_chat` hook SHALL return only budgeted, high-priority memory for the current query. Recall SHALL use the configured retrieval strategy: `fts` for exact SQLite FTS matching, or `hybrid` for local FTS plus vector ranking suitable for personalized questions. In hybrid mode the system SHALL build a unified candidate pool from FTS and vector recall, then apply the rerank stage (when enabled) before selecting the budgeted top-k for injection. When relevant L1 or L2 memory exists within budget, `before_chat` SHALL return a non-empty memory block with traceable snippets instead of silently falling back to no recall. Each stage SHALL degrade safely: rerank unavailable falls back to fused ordering; ANN unavailable falls back to cached-vector linear scoring; embeddings disabled falls back to hashed/FTS behavior.

#### Scenario: Default recall on a new message

- **WHEN** `memory_retrieval_enabled` is true
- **THEN** recall SHALL prioritize current session L2 summary, then L1 top-k matches, then optional cross-session L2 when routed
- **AND** recall SHALL NOT inject entire L0 archives by default

#### Scenario: Hybrid recall handles semantic personalization

- **WHEN** `memory_retrieval_strategy` is `hybrid`
- **AND** a user asks a personalization-sensitive question that does not share exact keywords with stored L1 preferences
- **THEN** the Memory brain SHALL retrieve relevant L1/L2 memories via the unified FTS+vector candidate pool
- **AND** the returned memory block SHALL include at least one relevant snippet when such memory exists within `memory_token_budget`

#### Scenario: Rerank selects top-k

- **WHEN** `rerank_enabled` is true and a candidate pool is produced
- **THEN** the Memory brain SHALL inject only the reranked top-k snippets within budget
- **AND** lower-ranked candidates SHALL be omitted

#### Scenario: Rerank disabled preserves fused ordering

- **WHEN** `rerank_enabled` is false or rerank is unavailable
- **THEN** the Memory brain SHALL order candidates by fused recall score
- **AND** recall SHALL still return budgeted top snippets

#### Scenario: FTS strategy remains available

- **WHEN** `memory_retrieval_strategy` is `fts`
- **THEN** the Memory brain SHALL use SQLite FTS recall behavior
- **AND** the system SHALL still proceed when no FTS match is found

#### Scenario: Memory budget is enforced

- **WHEN** recall returns more candidate memories than fit in `memory_token_budget`
- **THEN** the Memory brain SHALL include the highest-ranked snippets first
- **AND** lower-ranked snippets SHALL be omitted rather than exceeding the budget
