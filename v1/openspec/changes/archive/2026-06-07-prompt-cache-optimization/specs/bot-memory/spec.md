## MODIFIED Requirements

### Requirement: Tool-program retrieval before chat with token budget

Before calling the chat API, when `memory_retrieval_enabled` is true, the system SHALL run a backend search program (`search_memory`) against `index.sqlite` FTS—not a full directory walk—and inject top-k results within `memory_token_budget` as **dynamic context** per `context-cache-discipline`, not as an early stable system message.

#### Scenario: User sends message with retrieval on

- **WHEN** the user sends a message and memory retrieval is enabled
- **THEN** the backend SHALL FTS-search the index using the user message and optional session summary
- **AND** SHALL inject only matching snippets within the token budget in the dynamic context layer
- **AND** SHALL NOT load the entire `memory/` directory into the prompt
- **AND** SHALL NOT inject retrieval results into the stable system prompt before conversation history

#### Scenario: Retrieval disabled

- **WHEN** `memory_retrieval_enabled` is false or `memory_enabled` is false
- **THEN** no memory retrieval block SHALL be added to the API messages
- **AND** existing soul folder and session summary behavior SHALL remain unchanged
