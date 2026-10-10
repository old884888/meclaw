# memory-entry Specification

## Purpose
将记忆系统从碎片化 JSON 条目改为结构化 Markdown 文档，提升记忆完整性和信息密度，同时保留 FTS5 检索加速能力。

## Requirements

### Requirement: Structured Markdown entry format

Each memory entry SHALL be stored as a single Markdown file with YAML frontmatter at `memory/entries/{date}-{slug}.md`. The frontmatter SHALL contain `type`, `importance`, `keywords`, `related` (optional list of related entry filenames), and `created_at`. The body SHALL contain three sections: 摘要 (summary paragraph, 3-5 sentences), 要点 (key points, 3-8 bullet items), and 关键词 (keywords, 5-10 tags).

#### Scenario: Compression produces entry

- **WHEN** the user triggers context compression with memory extraction enabled
- **THEN** the system SHALL produce a single Markdown entry file under `memory/entries/`
- **AND** SHALL NOT produce multiple JSON碎片 files under `memory/items/`
- **AND** the entry SHALL contain摘要, 要点, and 关键词 sections

#### Scenario: Entry file naming

- **WHEN** a new entry is created
- **THEN** the file SHALL be named `{YYYY-MM-DD}-{slug}.md` where slug is derived from the entry title
- **AND** if a file with the same name exists, a numeric suffix SHALL be appended

### Requirement: YAML frontmatter metadata

Each entry file SHALL begin with a YAML frontmatter block containing metadata fields.

#### Scenario: Parse frontmatter

- **WHEN** the system reads an entry file
- **THEN** it SHALL parse the YAML frontmatter to extract `type`, `importance`, `keywords`, `related`, and `created_at`
- **AND** if frontmatter parsing fails, SHALL use default values (type=fact, importance=3, empty keywords, empty related)

### Requirement: Entry relationships via related field

Each entry MAY include a `related` field in its YAML frontmatter listing filenames of other entries that have a causal or parallel relationship. Relationships are one-directional and lightweight — no separate graph structure, no bidirectional enforcement.

#### Scenario: Compression annotates related entries

- **WHEN** the LLM produces a new entry during compression
- **AND** the current conversation clearly relates to a previous entry (causal or parallel)
- **THEN** the LLM MAY include the related entry's filename in the `related` field
- **AND** if no clear relationship exists, `related` SHALL be empty or omitted

#### Scenario: Retrieval pulls related entries

- **WHEN** FTS5 search matches an entry that has a non-empty `related` field
- **THEN** the system SHALL attempt to load the related entries as supplementary context
- **AND** related entries SHALL be appended after direct FTS matches, within the remaining token budget
- **AND** if a related entry file does not exist (deleted), it SHALL be silently skipped

#### Scenario: Deleted entry leaves orphaned references

- **WHEN** an entry is deleted
- **THEN** other entries that reference it in their `related` field SHALL NOT be modified
- **AND** the orphaned reference SHALL be silently skipped during retrieval

### Requirement: FTS5 index for entries

The system SHALL maintain `memory_entries_index` and `memory_entries_fts` tables in `index.sqlite` for full-text search over entry content. The `search_text` field SHALL combine keywords, 摘要, and 要点 with Chinese n-gram tokenization.

#### Scenario: Index after write

- **WHEN** a new entry file is written
- **THEN** the system SHALL insert a row into `memory_entries_index` and `memory_entries_fts`
- **AND** the `search_text` SHALL include keywords + 摘要 + 要点 + Chinese 2/3-grams

#### Scenario: Incremental reindex

- **WHEN** an entry file's mtime differs from the index
- **THEN** the system SHALL reindex that entry
- **AND** deleted entries SHALL be removed from the index

### Requirement: Retrieval returns complete entries

When searching memory, the system SHALL query `memory_entries_fts` (and fallback to `memory_items_fts` for legacy data) and return 2-3 complete entries within the token budget, instead of 20+ fragments.

#### Scenario: Search with entry format

- **WHEN** the system searches memory before sending a message
- **THEN** it SHALL query `memory_entries_fts` first
- **AND** SHALL return complete entry content (摘要 + 要点) rather than single-sentence fragments
- **AND** SHALL respect `memory_token_budget`

#### Scenario: Legacy fallback

- **WHEN** no entries match the query
- **THEN** the system SHALL fall back to querying `memory_items_fts` (legacy JSON items)
- **AND** SHALL format legacy results in the same entry-like display format

### Requirement: memory.md as index

The `memory.md` file in the soul folder root SHALL serve as an index of all entries, listing each entry's date, title, and one-sentence description. It SHALL NOT store full entry content.

#### Scenario: Update index on compression

- **WHEN** a new entry is created via compression
- **THEN** the system SHALL append a one-line index entry to `memory.md`
- **AND** the line format SHALL be `- {date} [{title}]({path}) — {one-sentence description}`

#### Scenario: memory.md size

- **WHEN** `memory.md` exceeds the configured cap
- **THEN** the system SHALL warn and skip auto-appending
- **AND** SHALL NOT truncate existing content

### Requirement: Extraction prompt outputs Markdown

The extraction prompt SHALL instruct the LLM to output a single Markdown document with YAML frontmatter, not a JSON array.

#### Scenario: Standard compression

- **WHEN** compression runs with standard detail level
- **THEN** the extraction prompt SHALL request a Markdown document with 摘要 + 要点 + 关键词
- **AND** the system SHALL parse the response as Markdown, not JSON

#### Scenario: Max detail compression

- **WHEN** compression runs with max detail level
- **THEN** the extraction prompt SHALL additionally request up to 3 quote-type entries
- **AND** quotes SHALL be included as additional要点 items or separate entries

### Requirement: Backward compatibility with legacy items

The system SHALL continue to read and index existing `memory/items/` JSON files. Legacy items SHALL be searchable via `memory_items_fts` but SHALL NOT be converted to the new format automatically.

#### Scenario: Mixed retrieval

- **WHEN** the user has both legacy items and new entries
- **THEN** the system SHALL search both `memory_entries_fts` and `memory_items_fts`
- **AND** SHALL prioritize entry results over item results
- **AND** SHALL NOT duplicate content across formats

#### Scenario: Legacy items preserved

- **WHEN** the system reads memory
- **THEN** existing `memory/items/` files SHALL NOT be deleted or modified
- **AND** the memory panel SHALL display both entries and items

### Requirement: Frontend adaptation

The memory panel SHALL display entries with their摘要 and要点, and legacy items with their existing format.

#### Scenario: Display entries

- **WHEN** the user opens the memory panel
- **THEN** entries SHALL be listed with date, title, and摘要
- **AND** clicking an entry SHALL expand to show要点 and关键词

#### Scenario: Display legacy items

- **WHEN** legacy items exist
- **THEN** they SHALL be displayed in a separate section below entries
- **AND** SHALL maintain their existing display format
