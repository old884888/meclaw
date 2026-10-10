## ADDED Requirements

### Requirement: Per-bot isolated memory directory and index

Each bot with a configured `soul_folder` SHALL have its own memory tree at `{soul_folder}/memory/` with category subfolders and a search index at `{soul_folder}/memory/index.sqlite`. Memory data MUST NOT be shared across bots unless explicitly migrated by the user.

#### Scenario: Active bot uses its soul folder

- **WHEN** the user sends a chat message with bot A active
- **THEN** memory read and write operations SHALL use bot A's `{soul_folder}/memory/`
- **AND** SHALL NOT read or write bot B's memory directory or index

#### Scenario: Bot without soul folder

- **WHEN** the active bot has no `soul_folder` configured
- **THEN** memory storage and retrieval SHALL be skipped
- **AND** chat SHALL proceed without memory injection

### Requirement: Category folders as human-readable source of truth

Short-to-medium term memories SHALL be stored as individual files under `{soul_folder}/memory/items/{type}/` where `type` is one of `fact`, `preference`, `project`, `relationship`, or `quote`. The sqlite index SHALL be synchronized from these files (dual-write).

#### Scenario: Write structured memory item

- **WHEN** the memory curator approves a candidate with a supported type
- **THEN** the system SHALL write a file under `memory/items/{type}/`
- **AND** SHALL update `memory/index.sqlite` FTS index for that file
- **AND** SHALL NOT require the user to manually edit sqlite

#### Scenario: User inspects memory on disk

- **WHEN** the user opens `memory/items/fact/` in a file manager
- **THEN** they SHALL see one file per memory entry in a readable format (JSON or markdown)

#### Scenario: Duplicate similar item

- **WHEN** a new candidate has high textual similarity to an existing item (rule-based threshold in Phase 1)
- **THEN** the system SHALL skip creating a new file by default
- **AND** SHALL NOT create duplicate entries for the same fact

### Requirement: memory.md as stable facts layer with auto-merge on compress

The existing `memory.md` in the soul folder root SHALL remain the layer for a small set of stable facts and core preferences, loaded at startup. The system SHALL enforce or warn on a documented size cap (e.g. 4KB). When context compression runs memory extraction, the system SHALL automatically merge elite entries (importance ≥ 4, type `fact` or `preference`, sufficient confidence) into `memory.md` as concise one-line bullets with deduplication, in addition to writing detail files under `memory/items/`.

#### Scenario: Load system prompt

- **WHEN** the system builds the system prompt for a bot with `memory.md`
- **THEN** `memory.md` content SHALL be included under the「长期记忆」section as today
- **AND** long document chunks SHALL NOT be appended to `memory.md` automatically

#### Scenario: Compress updates memory.md

- **WHEN** the user compresses context with memory write enabled
- **AND** extraction yields a high-importance stable fact or preference
- **THEN** the system SHALL append or merge a one-line entry into `memory.md`
- **AND** SHALL NOT paste full conversation text or long articles into `memory.md`

#### Scenario: Manual edit still allowed

- **WHEN** the user manually edits `memory.md` or uses `write_memory_file`
- **THEN** the system SHALL respect the edited content on next load
- **AND** automatic merge on compress SHALL deduplicate against existing lines

### Requirement: Tool-program retrieval before chat with token budget

Before calling the chat API, when `memory_retrieval_enabled` is true, the system SHALL run a backend search program (`search_memory`) against `index.sqlite` FTS—not a full directory walk—and inject top-k results as a separate system message, bounded by `memory_token_budget`.

#### Scenario: User sends message with retrieval on

- **WHEN** the user sends a message and memory retrieval is enabled
- **THEN** the backend SHALL FTS-search the index using the user message and optional session summary
- **AND** SHALL inject only matching snippets within the token budget
- **AND** SHALL NOT load the entire `memory/` directory into the prompt

#### Scenario: Retrieval disabled

- **WHEN** `memory_retrieval_enabled` is false or `memory_enabled` is false
- **THEN** no memory retrieval block SHALL be added to the API messages
- **AND** existing soul folder and session summary behavior SHALL remain unchanged

### Requirement: Retrieval scoring

Retrieved items SHALL be ranked using a composite score: FTS relevance (bm25), optional recency decay by type, and stored importance (1–5). Quote-type items SHALL NOT be heavily penalized by age.

#### Scenario: Rank mixed memory types

- **WHEN** multiple item types match a query
- **THEN** the system SHALL apply type-specific recency weighting
- **AND** SHALL return the highest-scoring items up to top-k within budget

### Requirement: Memory switches in configuration

The application SHALL support global and per-bot memory settings: `memory_enabled`, `memory_retrieval_enabled`, `memory_auto_extract` (default false in Phase 1), and `memory_token_budget`.

#### Scenario: Global memory off

- **WHEN** `memory_enabled` is false at global level and not overridden per bot
- **THEN** no memory extraction or retrieval SHALL run for any bot

#### Scenario: Per-bot override

- **WHEN** a bot entry sets `memory_enabled: false`
- **THEN** that bot SHALL skip memory operations even if global memory is enabled

### Requirement: Dual pipeline on context compression

When the user triggers context compression (`compress_context`), the system SHALL run two jobs: (1) conversation summary for the current session (existing behavior), and (2) memory extraction when `memory_enabled` is true and write is not read-only, producing structured candidates written to `memory/items/`, index updates, and optional `memory.md` merge.

#### Scenario: Manual compress with memory on

- **WHEN** the user compresses context with memory enabled and not read-only
- **THEN** the system SHALL update `current_summary` as today
- **AND** SHALL run memory extraction on the compressed segment
- **AND** SHALL write approved items to category folders and update the index
- **AND** SHALL merge elite facts into `memory.md` when applicable
- **AND** SHALL NOT write memory during streaming assistant output

#### Scenario: Low-quality candidate filtered

- **WHEN** extraction returns vague or session-ephemeral content (e.g. "user asked a question today")
- **THEN** the curator SHALL reject or mark `action: ignore`
- **AND** SHALL NOT persist such items

### Requirement: No short-term memory layer duplication

The system SHALL NOT add a separate short-term memory cache beyond existing `current_messages` and `current_summary`.

#### Scenario: Normal chat without compression

- **WHEN** the user chats within context limits
- **THEN** short-term context SHALL come from message history and optional session summary only
- **AND** no additional ephemeral memory layer SHALL be introduced
