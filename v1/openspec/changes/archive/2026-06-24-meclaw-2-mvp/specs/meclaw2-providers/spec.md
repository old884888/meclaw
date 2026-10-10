## ADDED Requirements

### Requirement: Multiple API profiles

The system SHALL allow multiple API supplier profiles each with id, name, base_url, api_key, model, and provider type.

#### Scenario: User creates a profile

- **WHEN** the user saves a new supplier with required fields
- **THEN** the profile SHALL be stored in `config.json`
- **AND** the profile SHALL appear in the supplier list on next load

### Requirement: Test connection uses profile model

The system SHALL test connectivity using the profile's own model name, not the active Bot's model override.

#### Scenario: User tests supplier

- **WHEN** the user clicks test connection for a profile configured with model `mimo-2.5`
- **THEN** the test request SHALL use `mimo-2.5`
- **AND** the UI SHALL show success or failure message

### Requirement: Provider types supported in MVP

The system SHALL support provider adapters for at least `generic` (OpenAI-compatible), `anthropic`, and `deepseek`.

#### Scenario: User selects Anthropic provider

- **WHEN** a profile has `provider` set to `anthropic`
- **THEN** outbound requests SHALL use Anthropic Messages API headers and endpoint rules

### Requirement: Text-only provider MVP

The MVP provider layer SHALL support normal text chat streaming and SHALL NOT require tool calling or reasoning UI.

#### Scenario: DeepSeek profile streams response

- **WHEN** a DeepSeek-compatible profile returns text streaming chunks
- **THEN** the chat UI SHALL display content tokens
- **AND** the MVP MAY ignore provider-specific reasoning fields

#### Scenario: Tool calling requested

- **WHEN** a future feature attempts to request tools in MVP
- **THEN** the provider layer SHALL NOT include `tools` or `tool_choice` in the request

### Requirement: Bot binds one profile

Each Bot SHALL reference exactly one `profile_id` for LLM calls unless overridden at Bot level for model only.

#### Scenario: Bot uses bound supplier

- **WHEN** the user chats with a Bot bound to profile P
- **THEN** chat completion SHALL use profile P's base_url and api_key

### Requirement: API key redaction

The system SHALL avoid exposing full API keys in logs, UI display, and error messages.

#### Scenario: Supplier list is displayed

- **WHEN** a profile with an API key is shown in the UI outside an edit field
- **THEN** the API key SHALL be redacted

#### Scenario: Provider request fails

- **WHEN** the backend returns an error message to the frontend
- **THEN** the error message SHALL NOT include the full API key
