## ADDED Requirements

### Requirement: Immediate assistant placeholder on send

The chat UI SHALL render an assistant message placeholder immediately after the user sends a message and before any model token is received.

#### Scenario: Placeholder appears on send

- **WHEN** the user sends a message and generation starts
- **THEN** the chat view SHALL display an assistant row with a visible loading indicator within the same render cycle as the user message

#### Scenario: Placeholder removed on completion without tokens

- **WHEN** generation ends with an error and no tokens were streamed
- **THEN** the placeholder SHALL be removed or replaced with the error assistant message without leaving a duplicate row

### Requirement: Generation status labels during pre-token latency

The chat UI SHALL display short status text describing the current generation phase before streaming begins.

#### Scenario: Default preparing status

- **WHEN** generation starts and no brain trace or token has arrived
- **THEN** the placeholder SHALL show a preparing status label equivalent to 「正在准备…」

#### Scenario: Memory retrieval status

- **WHEN** a `brain_trace` event is received for the active generation
- **THEN** the placeholder status label SHALL update to indicate memory retrieval (e.g. 「正在检索记忆…」)

#### Scenario: Long wait hint

- **WHEN** no token has arrived within a configured timeout (default 8 seconds)
- **THEN** the placeholder status label SHALL update to indicate the model is still pending (e.g. 「仍在等待模型响应…」)

### Requirement: Smooth transition to streaming

The chat UI SHALL transition from the waiting placeholder to streaming output without creating a second assistant message row for the same generation.

#### Scenario: First token reuses placeholder bubble

- **WHEN** the first `token` event arrives for the active generation
- **THEN** the same assistant bubble SHALL begin showing streamed content and the loading indicator SHALL be removed

#### Scenario: Streaming cursor during output

- **WHEN** tokens are being streamed
- **THEN** the assistant bubble SHALL show a streaming cursor until generation completes

### Requirement: Generating state disables duplicate sends

The chat UI SHALL prevent sending a new message while a generation is active, consistent with existing behavior.

#### Scenario: Send disabled during waiting

- **WHEN** a generation is active and only the placeholder is visible
- **THEN** the send control SHALL remain disabled until the generation completes or is stopped
