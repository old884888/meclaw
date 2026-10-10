# mnemos-rerank Specification

## Purpose
TBD - created by archiving change mnemos-vector-recall-rerank. Update Purpose after archive.
## Requirements
### Requirement: Pluggable rerank stage with selectable source

The system SHALL provide a pluggable rerank stage that scores a candidate pool against the query, with the source selectable via `rerank_provider` (`local`, `api`, or `off`).

#### Scenario: Local cross-encoder rerank

- **WHEN** `rerank_enabled` is true and `rerank_provider` is `local`
- **THEN** the system SHALL score candidates with a locally loaded cross-encoder identified by `rerank_model`
- **AND** scoring SHALL NOT require network access

#### Scenario: API LLM rerank

- **WHEN** `rerank_enabled` is true and `rerank_provider` is `api`
- **THEN** the system SHALL score candidates via the configured provider/model
- **AND** the call SHALL be bounded in candidate count by `rerank_candidate_pool`

#### Scenario: Rerank disabled

- **WHEN** `rerank_enabled` is false or `rerank_provider` is `off`
- **THEN** the system SHALL order candidates by the existing fused recall score
- **AND** no rerank call SHALL be made

### Requirement: Rerank narrows to budgeted top-k

After reranking, the system SHALL inject only the top-k highest-scored candidates within the memory token budget.

#### Scenario: Pool larger than top-k

- **WHEN** the reranked candidate pool is larger than `rerank_top_k`
- **THEN** only the top `rerank_top_k` candidates SHALL be considered for injection
- **AND** the memory token budget SHALL still bound the final injected set

#### Scenario: Fewer tokens after rerank

- **WHEN** rerank selects a small high-relevance top-k
- **THEN** the injected memory block SHALL contain only those snippets
- **AND** lower-relevance candidates SHALL be omitted rather than padding the budget

### Requirement: Rerank failures degrade safely

The rerank stage SHALL degrade without blocking chat when its source is unavailable or errors.

#### Scenario: Rerank source fails or is missing

- **WHEN** the rerank model/dependency cannot be loaded or the rerank call errors or times out
- **THEN** the system SHALL fall back to fused recall ordering without rerank
- **AND** chat assembly SHALL continue without raising

