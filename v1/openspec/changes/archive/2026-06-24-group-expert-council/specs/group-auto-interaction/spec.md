## ADDED Requirements

### Requirement: Auto-interaction suspended during council runs

While an expert council run is active for a user turn, the probabilistic auto-interaction logic (auto @-mention supplementation and Bot-chain reply rolls) SHALL be suspended and replaced by the council's round-based orchestration.

#### Scenario: Council orchestration takes over chaining

- **WHEN** a council run is active
- **THEN** `auto_mention_pct` and `auto_reply_pct` rolls SHALL NOT drive turn sequencing
- **AND** the council pipeline SHALL determine which Bot speaks in each round

#### Scenario: Free-chat resumes after council ends

- **WHEN** a council run completes or is stopped
- **THEN** subsequent normal group messages SHALL again use the existing auto-interaction probabilities
- **AND** the group's `auto_interaction_enabled` setting SHALL be unchanged by the council run

#### Scenario: Chain depth limit not consumed by council

- **WHEN** a council run executes its rounds
- **THEN** council rounds SHALL be bounded by the council's own round limit
- **AND** SHALL NOT be governed by `max_chain_rounds` of the free-chat reply chain
