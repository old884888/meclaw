## MODIFIED Requirements

### Requirement: Prompt assembly order is stable and cache-friendly

The orchestrator SHALL assemble messages in a stable order to support prompt caching discipline. When skill recall is enabled and task intent is detected, approved skill content MAY be injected as a dynamic block without modifying the stable system prefix.

#### Scenario: Messages are built for API call

- **WHEN** the orchestrator produces API messages
- **THEN** the order SHALL be: base system (soul) → persona block → memory block → optional skill block → optional cognitive block → session summary → conversation history → current user input
- **AND** each optional block SHALL be omitted entirely when its budget is zero or brain is inactive
- **AND** skill blocks SHALL include only approved skills within `skill_token_budget`
