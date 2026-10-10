## MODIFIED Requirements

### Requirement: L3 user profile is a compressed long-term persona input

The Memory brain SHALL maintain an L3 user profile used by the Persona brain and/or Memory brain as a short injected summary. When consolidation is enabled and profile capacity is exceeded, the system SHALL compress the profile while preserving pinned constraints and newer preferences.

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

- **WHEN** newer L1 memories conflict with older preferences
- **THEN** the L3 profile SHALL prefer the newer active preference in the injected summary
- **AND** older evidence SHALL remain traceable in L1/L0 rather than being deleted automatically

#### Scenario: Soul remains human-authored

- **WHEN** L3 profile is generated or refreshed
- **THEN** `soul.md` SHALL NOT be modified automatically
- **AND** generated profile content SHALL remain under the bot memory directory

#### Scenario: Profile capacity triggers consolidation

- **WHEN** profile content exceeds configured capacity threshold
- **AND** consolidation is enabled
- **THEN** the system SHALL compress redundant profile entries
- **AND** SHALL retain constraint-type facts at full fidelity
