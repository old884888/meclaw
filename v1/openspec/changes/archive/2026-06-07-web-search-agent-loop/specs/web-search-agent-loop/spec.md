## ADDED Requirements

### Requirement: Multi-round search_web agent loop

When web search is enabled, the backend SHALL execute `search_web` tool calls in a multi-round agent loop until the model returns a message without `tool_calls` or until `web_search_max_rounds` is reached.

#### Scenario: Model searches then refines

- **WHEN** the model returns `tool_calls` for `search_web` in round 1
- **AND** after tool results are appended the model returns additional `tool_calls` in round 2
- **THEN** the backend SHALL execute those searches
- **AND** SHALL continue the loop until no further `tool_calls` or the round limit is reached
- **AND** SHALL then produce the final assistant reply via streaming without tools

#### Scenario: Round limit reached

- **WHEN** the model still returns `tool_calls` after `web_search_max_rounds` rounds
- **THEN** the backend SHALL stop issuing new tool rounds
- **AND** SHALL proceed to the final streaming completion using messages accumulated so far
- **AND** SHALL log that the round limit was hit

#### Scenario: Single round sufficient

- **WHEN** the model returns `tool_calls` in round 1 and no `tool_calls` in round 2
- **THEN** the backend SHALL execute only round-1 searches
- **AND** SHALL stream the final reply after round 2's non-tool response path (direct to stream if round 2 has content only)

#### Scenario: Web search disabled

- **WHEN** web search is not enabled for the active bot
- **THEN** the request SHALL NOT enter the tool loop
- **AND** SHALL behave as a normal chat completion without `search_web` tools

### Requirement: Per-round query cap

The backend SHALL limit the number of `search_web` tool calls executed per round to `web_search_max_queries_per_round`.

#### Scenario: Model requests too many searches in one round

- **WHEN** a single assistant message contains more `search_web` tool calls than the configured per-round cap
- **THEN** the backend SHALL execute only the first N calls up to the cap
- **AND** SHALL log a warning for truncated calls
- **AND** SHALL still append tool responses for executed calls only

### Requirement: Reasoning between tool rounds

When the assistant message in a tool round includes `reasoning_content` (or provider-equivalent thinking field), the backend SHALL emit that reasoning to the frontend before or after executing searches in that round, consistent with existing stream reasoning behavior.

#### Scenario: Thinking between searches

- **WHEN** round 1 returns `reasoning_content` and `tool_calls`
- **THEN** the frontend SHALL receive reasoning tokens for that content
- **AND** the user SHALL see thinking content in the thinking block while search steps are also recorded

### Requirement: Configurable loop limits

The application SHALL expose `web_search_max_rounds` and `web_search_max_queries_per_round` in settings with documented defaults.

#### Scenario: Default configuration

- **WHEN** the user has not set loop limits in config
- **THEN** `web_search_max_rounds` SHALL default to 3
- **AND** `web_search_max_queries_per_round` SHALL default to 3

#### Scenario: User lowers rounds to one

- **WHEN** `web_search_max_rounds` is set to 1
- **THEN** at most one tool round SHALL run before the final stream
- **AND** behavior SHALL match legacy single-round web search semantics

### Requirement: Structured search result for UI

Each `search_web` execution SHALL produce a structured result containing at minimum: `query`, `provider`, `items` (list of `{index, title, url, snippet}`), `text_for_model`, and optional `error`.

#### Scenario: Successful search with hits

- **WHEN** the search provider returns web results
- **THEN** `items` SHALL contain up to 8 entries with title, url, and snippet
- **AND** `text_for_model` SHALL remain a human-readable text block for the tool role message
- **AND** the tool role message content SHALL use `text_for_model` only

#### Scenario: Search failure

- **WHEN** the search provider fails or returns no usable hits
- **THEN** `items` MAY be empty
- **AND** `text_for_model` SHALL describe the failure or empty result without inventing sources
- **AND** `error` MAY contain a short machine-readable reason

### Requirement: Function tool type only

The system MUST NOT send `type: "web_search"` native API tools; only `type: "function"` named `search_web` SHALL be used.

#### Scenario: Networking enabled

- **WHEN** web search is enabled for a chat request
- **THEN** the outbound payload SHALL include `SEARCH_WEB_TOOL` as a function tool
- **AND** SHALL NOT include `{"type": "web_search"}`
