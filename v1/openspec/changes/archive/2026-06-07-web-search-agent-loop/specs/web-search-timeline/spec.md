## ADDED Requirements

### Requirement: Persistent web search timeline in assistant bubble

During and after an assistant reply with web search activity, the UI SHALL display a persistent timeline at the top of the assistant message bubble listing each executed search step.

#### Scenario: Multiple searches in one reply

- **WHEN** the backend executes three `search_web` calls across one or more tool rounds
- **THEN** the timeline SHALL show three rows
- **AND** each row SHALL display a globe indicator, the label「联网检索」, and the query string
- **AND** rows SHALL NOT replace one another as new searches start

#### Scenario: Search in progress

- **WHEN** a search step starts
- **THEN** the corresponding timeline row SHALL show an in-progress state (spinner or equivalent)
- **WHEN** the search completes
- **THEN** the row SHALL update to show result count or failure without removing the row

#### Scenario: After stream completes

- **WHEN** the assistant message finishes streaming
- **THEN** the timeline SHALL remain visible in the finalized message
- **AND** SHALL be restorable when reloading session history

### Requirement: Web search step detail panel

The user SHALL be able to open a detail view for an individual timeline row.

#### Scenario: Open step detail

- **WHEN** the user activates a completed timeline row
- **THEN** a panel SHALL open showing the search parameters as JSON (`query`)
- **AND** SHALL show result entries as readable cards or rows (title, snippet, url)
- **AND** SHALL provide a collapsed「查看原始数据」section with raw structured JSON and truncated tool text

#### Scenario: Failed step detail

- **WHEN** the user opens a failed search step
- **THEN** the panel SHALL show the error or empty-result explanation
- **AND** SHALL NOT show fabricated result items

### Requirement: Citations drawer

The UI SHALL aggregate all result items from all search steps in a reply, deduplicate by URL, and expose them via a citations entry point.

#### Scenario: Show citation count

- **WHEN** at least one search step produced items with URLs
- **THEN** the assistant message SHALL show a control such as「共 N 条引用」where N is the deduplicated count
- **WHEN** no citations exist
- **THEN** the citations control SHALL be hidden or disabled

#### Scenario: Open citations list

- **WHEN** the user opens the citations control
- **THEN** a drawer or sheet SHALL list citations with stable indices 1..N
- **AND** each entry SHALL show title, snippet, and clickable URL

### Requirement: Frontend events for search steps

The backend SHALL push step-level updates to the frontend separately from ephemeral round-level status.

#### Scenario: Step append and update

- **WHEN** a `search_web` call starts
- **THEN** the backend SHALL invoke a frontend callback (e.g. `onWebSearchStep`) with phase `searching`, `stepId`, `query`, and `provider`
- **WHEN** the call completes
- **THEN** the same `stepId` SHALL be updated with phase `done` or `failed`, `resultCount`, and `items`

#### Scenario: Stream done carries persistence payload

- **WHEN** streaming completes for a message that used web search
- **THEN** `onStreamDone` SHALL include `webSearchSteps` and `citations` arrays sufficient to rebuild the timeline and citations UI on session reload

### Requirement: Round-level status for overall phase

The UI SHALL retain a concise round-level indicator for phases such as analyzing, skipped, and error, without hiding the step timeline.

#### Scenario: Model skips search

- **WHEN** web search is enabled but the model does not call `search_web`
- **THEN** the UI SHALL show a skipped/muted status explaining that no search ran
- **AND** the timeline SHALL remain empty

#### Scenario: API error before search

- **WHEN** the tool-loop API call fails before any search executes
- **THEN** the UI SHALL show an error status
- **AND** SHALL not show fake timeline rows

### Requirement: Human-first presentation

Default search UI SHALL prioritize human-readable labels and cards; raw JSON SHALL not be the primary visible content.

#### Scenario: Default detail view

- **WHEN** the user opens step detail for the first time
- **THEN** structured result cards SHALL be visible by default
- **AND** raw JSON SHALL be behind an explicit expand control
