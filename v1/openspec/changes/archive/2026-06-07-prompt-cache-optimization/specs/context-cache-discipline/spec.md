# context-cache-discipline Specification

## Purpose

Define stable-prefix context assembly rules for MeClaw API requests across private chat, code mode, and group chat to maximize prompt cache reuse and reduce prefill token cost.

## ADDED Requirements

### Requirement: Context layers for API message assembly

The system SHALL assemble API messages in three layers before conversation history: **stable** (persona, fixed skills, fixed rules, stable tools), **semi_stable** (group roster, project overview when hash unchanged), and **dynamic** (time, memory hits, session summary, trigger context, read files). Stable and semi_stable content MUST appear before dynamic content in every request.

#### Scenario: Stable layer excludes runtime values

- **WHEN** the system builds API messages for any session mode
- **THEN** the stable layer SHALL NOT contain timestamps, random IDs, per-turn memory retrieval results, session summaries, group trigger reasons, working directory paths, or read file contents

#### Scenario: Dynamic layer appended after semi_stable

- **WHEN** the system injects per-turn context such as memory hits or current time
- **THEN** that content SHALL be placed in the dynamic layer after stable and semi_stable blocks
- **AND** SHALL NOT be prepended into the stable system prompt

### Requirement: Fixed assembly order for cache matching

The system SHALL use a fixed assembly order: tools (when present) → stable system → semi_stable context blocks → dynamic context blocks → non-system conversation history → current user message. The implementation MUST document this order as a cache-matching constraint in code comments.

#### Scenario: Tools precede system messages

- **WHEN** web search tools are included in a request
- **THEN** the `tools` array SHALL be serialized before messages in the API payload
- **AND** tool definitions SHALL use a deterministic key order across requests

#### Scenario: History does not precede stable prefix

- **WHEN** prior conversation messages are included
- **THEN** they SHALL appear after all stable and semi_stable blocks
- **AND** dynamic per-turn blocks SHALL NOT be inserted before earlier turns in a way that mutates the stable prefix

### Requirement: Private chat dynamic context placement

For private chat sessions, the system SHALL keep bot soul content and fixed skill instructions in the stable system prompt. Memory retrieval results, session summary, and current time (when web search is enabled) SHALL be injected only in the dynamic layer.

#### Scenario: Memory retrieval not in stable system

- **WHEN** memory retrieval is enabled for a private chat message
- **THEN** retrieval results SHALL be injected in the dynamic layer
- **AND** SHALL NOT be added as an early system message before conversation history

#### Scenario: Web search time context is dynamic

- **WHEN** web search is enabled for a private chat request
- **THEN** current time context SHALL be injected in the dynamic layer for that turn only
- **AND** SHALL NOT be added to the stable system prompt

### Requirement: Code mode separates fixed rules from project state

In code mode, fixed programming rules SHALL remain in the stable system prompt. Working directory path, project overview, and read file contents SHALL be injected in semi_stable or dynamic layers respectively, not in the stable system prompt.

#### Scenario: Project overview uses hash reuse

- **WHEN** the working directory structure hash is unchanged since the last request in the session
- **THEN** the system SHALL reuse the cached project overview text for the semi_stable layer
- **AND** SHALL NOT regenerate overview text that changes the prefix unnecessarily

#### Scenario: Read files injected as dynamic context

- **WHEN** the programming session has files in `read_files`
- **THEN** file contents SHALL be injected in the dynamic layer with stable path ordering
- **AND** SHALL NOT be emitted as an early system message in the stable prefix

### Requirement: Group chat splits stable roster from turn trigger

For group chat, group name, member list, and @ format instructions SHALL be in the semi_stable layer. Per-turn trigger reason, replying bot identity, and user mention list SHALL be in the dynamic layer only.

#### Scenario: Trigger reason does not alter stable prefix

- **WHEN** a group bot reply is triggered because another member @ mentioned it
- **THEN** the trigger reason SHALL appear in the dynamic layer for that turn
- **AND** SHALL NOT modify the semi_stable group roster block

#### Scenario: Reply bot switch does not change stable prefix

- **WHEN** multiple bots reply sequentially in one group turn
- **THEN** switching `_reply_bot_id` SHALL only affect dynamic layer identity text
- **AND** SHALL NOT change stable or semi_stable blocks between sequential API calls in the same session

### Requirement: Stable tool serialization

When function tools are included, the system SHALL serialize tool definitions with deterministic field ordering. Tools MUST NOT be included in requests that do not require tool calling for that turn.

#### Scenario: Non-web-search request has no tools

- **WHEN** web search is disabled for the active bot
- **THEN** the API payload SHALL NOT include a `tools` field
- **AND** stable prefix content SHALL remain identical aside from intentional persona differences per bot

#### Scenario: Web search tool definition is stable

- **WHEN** web search is enabled and tools are attached
- **THEN** the `search_web` tool schema SHALL be identical across requests for the same bot configuration
- **AND** SHALL NOT embed runtime values such as timestamps in the tool description

### Requirement: Optional cache usage logging

When the API response includes prompt cache usage fields, the system SHALL log cache read and cache creation token counts and compute a hit rate for debugging.

#### Scenario: Cache fields present in usage

- **WHEN** the API returns cache-related usage fields
- **THEN** the backend SHALL log hit rate as `cache_read / (cache_read + cache_creation)` when denominators are available
- **AND** SHALL continue normal chat flow if fields are absent
