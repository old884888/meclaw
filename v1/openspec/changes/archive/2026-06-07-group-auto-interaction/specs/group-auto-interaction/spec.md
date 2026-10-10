# group-auto-interaction

Bot-to-bot @ chaining, hybrid mention generation, and per-group probability settings.

## ADDED Requirements

### Requirement: Group auto-interaction master switch

Each group SHALL support an `auto_interaction_enabled` setting that controls whether Bot messages can trigger further Bot replies via parsed @-mentions.

#### Scenario: Auto interaction disabled

- **WHEN** `auto_interaction_enabled` is false
- **THEN** Bot messages SHALL still display @-mentions in content
- **AND** parsed @-mentions in Bot messages SHALL NOT enqueue further Bot API replies

#### Scenario: Auto interaction enabled

- **WHEN** `auto_interaction_enabled` is true
- **THEN** parsed @-mentions of member Bots in assistant messages MAY enqueue further replies subject to `auto_reply_pct`

### Requirement: Per-member mention and reply probabilities

Each group member Bot SHALL have configurable `auto_mention_pct` and `auto_reply_pct` values from 0 to 100.

#### Scenario: Auto reply roll for Bot-originated mention

- **WHEN** an assistant message parses an @-mention targeting member Bot B
- **AND** the mention was not part of a user message with `mention_bot_ids` (i.e. Bot-chain origin)
- **THEN** the system SHALL roll against B's `auto_reply_pct`
- **AND** SHALL enqueue B only if the roll succeeds

#### Scenario: User mention ignores auto reply probability

- **WHEN** the user sends a message with `mention_bot_ids` including Bot B
- **THEN** Bot B SHALL reply regardless of `auto_reply_pct`

### Requirement: Hybrid mention generation

The system SHALL use model-generated @-mentions as the primary source and MAY supplement with programmatic mention when the model omits @.

#### Scenario: Model includes @-mention

- **WHEN** an assistant reply text contains parseable @-mentions of member Bots
- **THEN** those mentions SHALL be used for chaining without requiring `auto_mention_pct`

#### Scenario: Model omits @-mention but mention roll succeeds

- **WHEN** `auto_interaction_enabled` is true
- **AND** the speaking Bot's `auto_mention_pct` roll succeeds
- **AND** the assistant text contains no parseable Bot @-mention
- **THEN** the system SHALL append or merge an @-mention chosen via model-guided selection (not purely random member pick)
- **AND** SHALL parse the final text for chaining targets

### Requirement: Model-guided @ target selection

@-mention targets in Bot replies SHALL be chosen by the model via prompt guidance, then parsed from text.

#### Scenario: Group system prompt instructs @ usage

- **WHEN** a Bot generates a group reply
- **THEN** the group context system prompt SHALL instruct the model it may @ other members or @用户
- **AND** parsed member names SHALL map to `bot_id` using the group's member list

### Requirement: Serial reply chain for multiple mentions

Multiple @-mentioned Bots SHALL be replied to serially in queue order.

#### Scenario: User mentions A and B

- **WHEN** the user message mentions Bot A and Bot B
- **THEN** Bot A SHALL complete its reply before Bot B begins

#### Scenario: Bot chain enqueue

- **WHEN** a Bot reply parses @-mentions of B and C
- **AND** both pass `auto_reply_pct`
- **THEN** B and C SHALL be enqueued and processed one at a time in mention order

### Requirement: User mention is decorative only

@-mentions of the human user SHALL be informational and SHALL NOT trigger API calls.

#### Scenario: User @用户 in composer

- **WHEN** the user selects @用户 in the group composer
- **THEN** the message SHALL be stored and displayed with a user mention marker
- **AND** SHALL NOT trigger any Bot reply by itself

#### Scenario: Bot @用户 in reply text

- **WHEN** an assistant message contains `@用户`
- **THEN** the UI SHALL render it as a decorative mention
- **AND** SHALL NOT enqueue API calls for the user

### Requirement: Chain depth limit

The system SHALL limit Bot-to-Bot chain rounds per user message to prevent runaway loops.

#### Scenario: Chain limit reached

- **WHEN** Bot-chain rounds reach `max_chain_rounds` for the current user turn
- **THEN** no further Bot-chain replies SHALL be enqueued until the user sends a new message
