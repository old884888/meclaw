## Why

After the user sends a message, MeClaw2 shows no assistant feedback until the first model token arrives. During memory retrieval, brain trace assembly, and provider latency, the chat appears frozen. This hurts perceived responsiveness and makes long-prompt generations feel broken.

## What Changes

- Insert an immediate assistant placeholder bubble when `send` is dispatched (before first token).
- Drive placeholder copy through a small generation state machine (`preparing` → `retrieving_memory` → `waiting_model` → `streaming`).
- Reuse the same bubble DOM when the first token arrives to avoid layout jump.
- Add a subtle loading animation (dots or pulse) and optional timeout hint after N seconds with no events.
- Wire `brain_trace` WebSocket events to update placeholder status text when memory retrieval runs.

## Capabilities

### New Capabilities

- `meclaw2-chat-generation-ui`: Chat generation waiting states, placeholder bubble, and status animation during pre-token latency.

### Modified Capabilities

- None.

## Impact

- Affected frontend:
  - `meclaw2/web/app.js` (send flow, WebSocket handler, streaming bubble lifecycle)
  - `meclaw2/web/index.html` or CSS for loading animation styles
- No backend API changes required for MVP (uses existing `brain_trace` and `token` events).
- No breaking changes to message persistence or WebSocket protocol.
