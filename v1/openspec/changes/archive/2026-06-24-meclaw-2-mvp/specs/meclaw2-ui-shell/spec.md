## ADDED Requirements

### Requirement: Desktop two-column shell

The UI SHALL present a fixed sidebar (approximately 260px) and a main chat column with header, message area, and composer.

#### Scenario: User opens 2.0 home

- **WHEN** the application loads at default viewport width ≥ 900px
- **THEN** the user SHALL see sidebar navigation and main chat area simultaneously
- **AND** a settings control SHALL be visible in the header

### Requirement: Bot-first sidebar navigation

The sidebar SHALL use a two-level navigation: Bot list, then session list for the selected Bot.

#### Scenario: User browses bots

- **WHEN** the user is on the default sidebar view
- **THEN** the sidebar SHALL list all configured Bots with avatar and name
- **AND** clicking a Bot SHALL show only that Bot's sessions with a back control

### Requirement: Bot locked during active session

While a session is open, the header SHALL display the session's Bot as read-only.

#### Scenario: User chats in a session

- **WHEN** `currentSessionId` is set to an existing session
- **THEN** the header SHALL show that Bot's identity without allowing Bot switch for that session

### Requirement: Settings entry for suppliers and bots

The settings UI SHALL provide access to API supplier configuration and Bot management in MVP.

#### Scenario: User opens settings

- **WHEN** the user activates the settings control
- **THEN** the UI SHALL offer at least 「供应商」 and 「机器人」 sections
- **AND** memory and group chat sections SHALL appear disabled or labeled as coming soon

### Requirement: Dark theme default

The MVP UI SHALL use a dark color theme as the default visual style.

#### Scenario: First launch appearance

- **WHEN** the user opens the app for the first time
- **THEN** background and text colors SHALL follow the dark theme without requiring user configuration
