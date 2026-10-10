# meclaw2-history-persistence Specification

## Purpose
TBD - created by archiving change history-session-backup. Update Purpose after archive.
## Requirements
### Requirement: Rolling backup on session message writes

The system SHALL create rolling backup copies before overwriting a session message file.

#### Scenario: Backup created on message save

- **WHEN** messages are saved for an existing session file
- **THEN** the system SHALL preserve the previous file contents as a rotated backup before writing the new content

#### Scenario: Backup rotation limit

- **WHEN** the number of backup generations exceeds the configured limit (default 3)
- **THEN** the system SHALL discard the oldest backup file

### Requirement: Sessions index backup

The system SHALL apply the same rolling backup policy to the sessions index file when it is rewritten.

#### Scenario: Index backup on session list update

- **WHEN** `sessions.json` is updated and a previous version exists
- **THEN** the system SHALL rotate backups using the same generation limit as session message files

### Requirement: Configurable backup generations

The system SHALL allow operators to configure how many backup generations to retain.

#### Scenario: Default backup count

- **WHEN** no `history_backup_generations` is set in config
- **THEN** the system SHALL retain 3 backup generations per file

### Requirement: Operator visibility

The system SHALL expose backup policy information for operators.

#### Scenario: Data info includes backup policy

- **WHEN** an operator requests system data info
- **THEN** the response SHALL include the configured backup generation count

