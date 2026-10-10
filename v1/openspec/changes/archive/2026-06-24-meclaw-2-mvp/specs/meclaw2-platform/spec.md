## ADDED Requirements

### Requirement: Independent meclaw2 project root

The system SHALL run as a separate project directory `meclaw2/` without modifying MeClaw 1.0 startup paths.

#### Scenario: Developer starts 2.0

- **WHEN** the user runs the documented 2.0 start command
- **THEN** only `meclaw2/` backend and web assets SHALL be used
- **AND** MeClaw 1.0 `main.py` SHALL remain runnable in parallel

### Requirement: Local data directory

The system SHALL persist all user data under a configurable local data root defaulting to `meclaw2/data/`.

#### Scenario: Application restart

- **WHEN** the user restarts the 2.0 server after creating bots and sessions
- **THEN** `config.json`, `history/`, and `souls/` SHALL still exist under the data root
- **AND** previously saved sessions SHALL be loadable

### Requirement: HTTP and WebSocket API surface

The system SHALL expose REST endpoints for configuration and CRUD and a WebSocket endpoint for streaming chat.

#### Scenario: Frontend loads without pywebview

- **WHEN** a browser opens the 2.0 origin URL
- **THEN** static web UI SHALL load via HTTP
- **AND** chat SHALL communicate through WebSocket without `pywebview.api`

### Requirement: Environment override for data path

The system SHALL support `MECLAW2_DATA_DIR` to override the default data directory.

#### Scenario: Custom data location

- **WHEN** `MECLAW2_DATA_DIR` is set to an absolute path before server start
- **THEN** config and history SHALL be read and written under that path

### Requirement: First-run bootstrap

The system SHALL initialize a usable local data skeleton when the data directory is empty.

#### Scenario: Empty data directory

- **WHEN** the server starts with no `config.json`
- **THEN** the system SHALL create `config.json` with `schema_version` and memory placeholders
- **AND** the system SHALL create at least one default Bot and `souls/default/soul.md`
- **AND** the frontend SHALL guide the user to configure an API profile before chat is allowed

### Requirement: Bootstrap API

The system SHALL provide a bootstrap endpoint for frontend initialization.

#### Scenario: Frontend initializes

- **WHEN** the frontend calls `GET /api/bootstrap`
- **THEN** the response SHALL include config, bots, providers, active_bot_id, and setup readiness

### Requirement: Atomic local writes

The system SHALL write critical JSON files atomically to avoid corrupting user data.

#### Scenario: Config is saved

- **WHEN** the backend saves `config.json`
- **THEN** it SHALL write to a temporary file first
- **AND** replace the target file atomically after the temporary file is complete

### Requirement: Localhost-only default

The server SHALL bind to loopback by default and SHALL NOT expose APIs to the local network unless explicitly configured.

#### Scenario: User starts MVP server

- **WHEN** the user runs the documented MVP start command
- **THEN** the server SHALL listen on `127.0.0.1`
- **AND** CORS SHALL NOT allow all origins by default
