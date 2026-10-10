## Why

MeClaw2 currently disables DeepSeek thinking at the provider layer and discards any reasoning stream fields. Users cannot enable deep reasoning, choose intensity, or inspect the model's thinking process. This limits quality on hard tasks and hides useful transparency that competitor UIs provide.

## What Changes

- Add bot-level reasoning settings: `reasoning_enabled`, `reasoning_level` (`off` | `low` | `medium` | `high`), `reasoning_visible`.
- Map levels to provider-specific parameters (DeepSeek `thinking.type`, generic OpenAI-style `reasoning_effort`, Anthropic thinking budget).
- Parse and stream reasoning tokens separately from answer tokens via WebSocket `reasoning_token` events.
- Persist reasoning content on assistant messages in a separate field (excluded from next-turn context and memory extraction).
- Add collapsible thinking panel in chat UI with settings controls in bot editor.

## Capabilities

### New Capabilities

- `meclaw2-reasoning-output`: Reasoning configuration, provider mapping, streaming, persistence, and UI panel.

### Modified Capabilities

- `mnemos-context-cache-discipline`: Reasoning payloads may affect prefix cache hit rate; document opt-in trade-off when reasoning is enabled.

## Impact

- Affected backend:
  - `meclaw2/backend/adapters/providers.py` (payload build, SSE parse)
  - `meclaw2/backend/main.py` (`_run_generation`, message schema)
  - `meclaw2/backend/storage/history_store.py` (`make_message` reasoning field)
  - `meclaw2/backend/storage/config_store.py` (bot reasoning fields)
- Affected frontend:
  - `meclaw2/web/app.js`, `meclaw2/web/index.html` (thinking panel, settings)
- Cost/latency increase when reasoning enabled; cache hit rate may drop.
