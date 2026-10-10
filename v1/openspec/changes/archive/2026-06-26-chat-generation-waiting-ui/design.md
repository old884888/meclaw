## Context

MeClaw2 chat uses WebSocket events (`send` → optional `brain_trace` → `token` → `done`). The frontend only creates the assistant bubble on the first `token`, leaving a silent gap during server-side preparation. Users perceive this as a hang, especially with memory retrieval enabled.

Current relevant code:
- `sendMessage()` in `meclaw2/web/app.js` sets `setGenerating(true)` but renders no assistant row.
- `ensureStreamingBubble()` is called only from the `token` handler.
- `brain_trace` is already emitted before streaming when `brain_trace_enabled` is true.

## Goals / Non-Goals

**Goals:**
- Show immediate visual feedback after send (within one animation frame).
- Communicate progress through short status labels tied to known pipeline stages.
- Transition smoothly from waiting state to streaming without DOM replacement flicker.
- Keep implementation frontend-only for MVP.

**Non-Goals:**
- New backend WebSocket events (e.g. explicit `generation_started`) in this change.
- Reasoning/thinking panel (separate change).
- Group chat or multi-bot generation UX.

## Decisions

### Decision: Single placeholder bubble reused for streaming

Create one assistant wrap on send with a `.msg-waiting` state. On first token, remove waiting chrome and attach `.msg-body` + cursor in the same wrap.

**Alternative considered:** Separate loading row removed on first token. Rejected because it causes scroll jump and duplicate assistant rows.

### Decision: Client-side generation state machine

States: `idle` → `waiting` → `retrieving` (on brain_trace) → `streaming` (on token) → `idle`.

Status copy (Chinese):
- `waiting`: 「正在准备…」
- `retrieving`: 「正在检索记忆…」
- `streaming`: hide status, show cursor

**Alternative considered:** Server-driven status events. Deferred to keep scope minimal; brain_trace is sufficient for memory stage.

### Decision: Timeout hint at 8 seconds

If no token after 8s, update status to 「仍在等待模型响应…」 without changing layout.

### Decision: CSS-only animation

Use three-dot pulse via CSS keyframes on `.msg-waiting-dots`. No new JS animation engine dependency.

## Risks / Trade-offs

- [Risk] brain_trace disabled → user only sees generic 「正在准备…」 until token. → Acceptable; still better than blank.
- [Risk] Very fast responses may flash placeholder briefly. → Mitigation: min display 200ms optional; skip if adds complexity.
- [Risk] Error before token leaves orphan placeholder. → Clear placeholder on `error` / `done` without token in existing error handler.

## Migration Plan

Frontend-only deploy. No data migration. Rollback: revert `app.js` + CSS.

## Open Questions

- Should min-display debounce (200ms) be included in MVP? Default: no, ship simple first.
