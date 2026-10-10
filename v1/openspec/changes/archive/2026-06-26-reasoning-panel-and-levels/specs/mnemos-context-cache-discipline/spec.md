## ADDED Requirements

### Requirement: Reasoning mode cache trade-off disclosure

The system SHALL surface that enabling reasoning may reduce prefix cache hit rate compared to reasoning-off chat.

#### Scenario: Brain status notes reasoning cache impact

- **WHEN** a bot has reasoning enabled for a generation
- **THEN** brain status or settings UI SHALL indicate that reasoning mode may affect prompt cache efficiency
