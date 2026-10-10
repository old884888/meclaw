## ADDED Requirements

### Requirement: No invalid web_search tool type in API payload

The system MUST NOT send OpenAI/DeepSeek tools with `type: "web_search"` to chat completions endpoints that only accept `type: "function"`.

#### Scenario: Enable networking skill

- **WHEN** the user enables the「联网搜索」skill or equivalent bot flag
- **THEN** the outbound API payload SHALL NOT include `{"type": "web_search"}`
- **AND** SHALL use function tools or no tools if search is disabled

### Requirement: search_web function tool

When web search is enabled for a DeepSeek-compatible chat request, the system SHALL register a function tool named `search_web` with a query parameter and handle tool calls in an agent loop.

#### Scenario: Model requests search

- **WHEN** the model returns a tool call for `search_web` with a query string
- **THEN** the backend SHALL execute a configured search provider
- **AND** SHALL append a tool role message with results to the conversation
- **AND** SHALL call the chat API again until a final assistant message is produced or a loop limit is reached

#### Scenario: Search disabled

- **WHEN** web search is not enabled for the active bot
- **THEN** the request SHALL NOT include the `search_web` tool definition

### Requirement: Search provider configuration

The application SHALL support at least one built-in search backend without requiring MCP, with optional API key configuration for premium providers.

#### Scenario: Default provider without API key

- **WHEN** no external search API key is configured
- **THEN** the system SHALL use the default no-key or bundled search implementation documented in settings
- **AND** SHALL surface errors clearly if search fails

#### Scenario: Optional API key provider

- **WHEN** the user configures a supported search API key in settings
- **THEN** subsequent `search_web` executions SHALL use that provider

### Requirement: Web search skill alignment

The「联网搜索」skill instructions SHALL describe function-based search behavior, not a native `web_search` API tool type.

#### Scenario: Skill enabled in composer or settings

- **WHEN** `web-search` is in the enabled skills list
- **THEN** `search_web` function tooling SHALL be eligible for the next chat request (DeepSeek provider)
- **AND** skill text SHALL NOT claim unsupported API tool types

### Requirement: MCP as future extension only

MCP-based search connectors SHALL NOT be required for basic web search in this change.

#### Scenario: User without MCP setup

- **WHEN** the user has not configured any MCP server
- **THEN** enabling联网 SHALL still work via built-in `search_web` if a search backend is available
