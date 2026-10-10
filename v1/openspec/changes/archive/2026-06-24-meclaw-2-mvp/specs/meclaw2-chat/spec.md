## ADDED Requirements

### Requirement: Send user message

The user SHALL send text messages in the active session composer.

#### Scenario: Successful send

- **WHEN** the user submits non-empty text while not generating
- **THEN** a user message SHALL be appended to the session history
- **AND** the UI SHALL show the user message in the chat area

### Requirement: Streaming assistant reply

The system SHALL stream assistant tokens to the client over WebSocket during generation.

#### Scenario: Model streams tokens

- **WHEN** the LLM returns a streaming response
- **THEN** the client SHALL receive incremental token events
- **AND** the assistant bubble SHALL grow until completion

### Requirement: Generation id for streaming lifecycle

Every chat generation SHALL be identified by a client-provided `generation_id`.

#### Scenario: Client sends a message

- **WHEN** the client sends a WebSocket `send` event
- **THEN** the event SHALL include `generation_id`, `session_id`, and `content`
- **AND** all `token`, `done`, `stopped`, and `error` events for that generation SHALL include the same `generation_id`

### Requirement: Stop generation

The user SHALL be able to stop an in-progress generation.

#### Scenario: User clicks stop

- **WHEN** the user activates stop during streaming
- **THEN** the backend SHALL abort the LLM request
- **AND** partial assistant content SHALL be retained in the session

### Requirement: Partial message persistence on stop

Stopped assistant output SHALL be persisted as a partial message.

#### Scenario: User stops generation after tokens arrived

- **WHEN** the backend stops a generation with partial assistant text
- **THEN** the session message file SHALL contain an assistant message with `status` set to `stopped`
- **AND** the frontend SHALL show the partial content after reload

### Requirement: Single active generation in MVP

The MVP system SHALL allow at most one active generation per backend process.

#### Scenario: Send while already generating

- **WHEN** a generation is active and the client sends another `send` event
- **THEN** the backend SHALL reject the new send with an error event
- **AND** the existing generation SHALL continue unless stopped

### Requirement: System prompt from soul without memory

Chat message assembly SHALL include the Bot soul system block and SHALL NOT include memory retrieval content in MVP.

#### Scenario: Chat with two different bots

- **WHEN** the user chats with Bot A and Bot B having different `soul.md`
- **THEN** replies SHALL reflect distinct system prompts per Bot

### Requirement: Persist assistant message

After generation completes, the assistant message SHALL be saved to the session message file.

#### Scenario: Stream completes

- **WHEN** the server emits a done event
- **THEN** the full assistant message SHALL be persisted
- **AND** reloading the session SHALL show the assistant message

### Requirement: Assistant message status

Assistant messages SHALL include a status field indicating completion state.

#### Scenario: Normal stream completes

- **WHEN** a generation completes normally
- **THEN** the persisted assistant message SHALL have `status` set to `done`

#### Scenario: API error occurs

- **WHEN** a generation fails after the user message is saved
- **THEN** the frontend SHALL receive an error event
- **AND** the implementation SHALL consistently either persist an assistant message with `status` set to `error` or omit assistant persistence for errors

### Requirement: Basic usage hint

The UI SHALL show a simple context usage hint such as message count in the composer area.

#### Scenario: Long conversation

- **WHEN** a session has more than ten messages
- **THEN** the composer area SHALL display the approximate message count
