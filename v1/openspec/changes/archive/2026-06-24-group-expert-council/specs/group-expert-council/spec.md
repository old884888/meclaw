## ADDED Requirements

### Requirement: Council mode activation on a group session

The system SHALL allow starting an expert council run on an existing group session for a single user topic, distinct from free-form @-mention chat. A council run SHALL require the group to have at least 2 member Bots.

#### Scenario: User starts a council run

- **WHEN** the user enables the「专家会议」switch in a group composer and sends a topic
- **THEN** the system SHALL begin a round-based council pipeline over the group's member Bots
- **AND** SHALL NOT use the probabilistic free-chat reply chain for that turn

#### Scenario: Insufficient members

- **WHEN** a council run is requested on a group with fewer than 2 member Bots
- **THEN** the system SHALL reject the run with an explanatory message
- **AND** SHALL NOT call any model

### Requirement: Round-based cognitive pipeline

A council run SHALL execute fixed-order rounds: Round 1 独立诊断 (independent diagnosis), Round 2 交叉澄清 (anonymized cross clarification), Round 3 红队攻击 (red-team critique), Round 4 架构师整合 (synthesis). Each round SHALL have an explicit cognitive goal and output contract.

#### Scenario: Rounds execute in fixed order

- **WHEN** a council run proceeds
- **THEN** the system SHALL run Round 1 → 2 → 3 → 4 in order
- **AND** SHALL push each round's outputs to the frontend as that round completes

#### Scenario: Round 1 independent and anchor-free

- **WHEN** Round 1 (独立诊断) runs
- **THEN** each expert Bot SHALL receive the same topic and produce `Root_Cause` + `Solution_Draft` + `Confidence`
- **AND** each expert Bot SHALL NOT be shown other experts' Round 1 outputs

#### Scenario: Round 2 clarification only

- **WHEN** Round 2 (交叉澄清) runs
- **THEN** drafts SHALL be presented anonymized (author identity hidden)
- **AND** reviewers SHALL only produce clarifying questions, NOT rebuttals or scores

#### Scenario: Round 3 red-team critique

- **WHEN** Round 3 (红队攻击) runs
- **THEN** the red-team role SHALL output, per draft, the most likely failure path, required resources, and falsifying evidence

#### Scenario: Round 4 forced synthesis

- **WHEN** Round 4 (架构师整合) runs
- **THEN** the synthesizer role SHALL output 1-3 hybrid options plus a decision matrix and a single explicit recommendation
- **AND** SHALL NOT return a "各有优劣" non-decision

### Requirement: Role assignment with fallback personas

The system SHALL assign council roles (experts, red-team, synthesizer) from group member Bots, and SHALL provide a fallback temporary persona when a required role has no assigned member.

#### Scenario: Members fill roles

- **WHEN** a council run starts and members are assigned to roles
- **THEN** each assigned Bot SHALL act in its role using its own persona (`soul.md`)

#### Scenario: Missing role fallback

- **WHEN** a required role (e.g. red-team or synthesizer) has no assigned member
- **THEN** the system SHALL use a built-in temporary role persona to fill it
- **AND** SHALL label that contribution as a system-provided role in the output

#### Scenario: Red-team independence

- **WHEN** a Bot is acting as red-team for a given round
- **THEN** that Bot SHALL critique drafts it did not author whenever possible

### Requirement: Confidence and basis tagging

Each Bot output in any round SHALL include a confidence score (0-100) and a basis type (推理 / 事实 / 假设 / 类比).

#### Scenario: Output carries confidence

- **WHEN** any council Bot produces a round output
- **THEN** the stored and displayed output SHALL include `Confidence` and `Basis` fields
- **AND** missing or unparseable tags SHALL default to a neutral confidence with basis 假设

### Requirement: Human arbitration checkpoint

After Round 4 synthesis, the council SHALL pause for human arbitration before any optional execution-detailing round.

#### Scenario: Pause for user decision

- **WHEN** Round 4 produces hybrid options
- **THEN** the run SHALL pause and present the options to the user
- **AND** SHALL NOT auto-proceed to execution detailing without user selection

#### Scenario: User selects a direction

- **WHEN** the user selects a direction or requests deepening
- **THEN** the system MAY run an execution-detailing round producing milestones, resource budget, risk mitigation, and acceptance criteria

### Requirement: Council run cost bounds

The system SHALL bound council cost by limiting per-run model calls and applying blackboard-based context compression.

#### Scenario: Round and member bounds enforced

- **WHEN** a council run executes
- **THEN** the number of model calls SHALL be bounded by member count and a configured round limit
- **AND** later rounds SHALL read the shared blackboard snapshot plus current-round inputs rather than full transcript history

#### Scenario: User stop interrupts council

- **WHEN** the user triggers stop during a council run
- **THEN** the system SHALL halt remaining rounds
- **AND** SHALL retain already-produced round outputs and the latest blackboard

### Requirement: Council output persisted to group memory

On council completion, the system SHALL write a consensus snapshot to the group's memory store.

#### Scenario: Consensus snapshot saved

- **WHEN** a council run completes Round 4 (or is stopped after producing a recommendation)
- **THEN** a consensus snapshot SHALL be written to `groups/{group_id}/memory/entries/`
- **AND** SHALL be retrievable by later group memory search
