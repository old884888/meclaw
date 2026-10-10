## Context

`providers.build_payload()` currently forces DeepSeek `thinking: {type: disabled}`. SSE parsers only yield `delta.content`. Chat WS emits only `token` events. `providers.py` header notes "reasoning UI are out of scope" — this change removes that limitation.

## Goals / Non-Goals

**Goals:**
- Unified `reasoning_level` API across providers with graceful degradation.
- Separate reasoning stream from answer stream end-to-end.
- Reasoning excluded from API message history on subsequent turns.
- UI panel default collapsed; user can expand during/after generation.

**Non-Goals:**
- Reasoning for background/L1 extraction jobs in this change.
- Group chat reasoning aggregation.
- Storing reasoning in L1 memory.

## Decisions

### Decision: Three bot-level fields

| Field | Type | Default |
|-------|------|---------|
| `reasoning_enabled` | bool | false |
| `reasoning_level` | off/low/medium/high | off |
| `reasoning_visible` | bool | true |

Effective level = `off` when `reasoning_enabled` is false.

### Decision: Provider mapping table in providers layer

- **DeepSeek** (`has_optimization deepseek`): `thinking.type` = enabled/disabled; level maps to supported strength if API exposes it, else enabled only.
- **OpenAI-compatible generic**: pass `reasoning_effort` when level != off (ignore if provider rejects).
- **Anthropic**: `thinking: {type: enabled, budget_tokens}` scaled by level (low=1k, medium=4k, high=8k defaults).

When unsupported: skip reasoning params, emit UI warning in brain status.

### Decision: WebSocket event `reasoning_token`

Mirror `token` event shape: `{event, generation_id, text}`. Frontend renders into `.msg-reasoning-body` above answer body.

### Decision: Message persistence

`make_message()` adds optional `reasoning: str`. `_append_assistant_message` stores it. Context builder for next turn uses `content` only, not `reasoning`.

### Decision: Replace hardcoded thinking disabled

Remove unconditional `thinking: disabled` when reasoning enabled; when off, keep current disabled behavior for DeepSeek cache stability.

## Risks / Trade-offs

- [Risk] Prefix cache invalidation when toggling reasoning. → Document in settings; default off.
- [Risk] Provider API differences break parsing. → Feature-detect per provider; fallback to content-only.
- [Risk] Large reasoning blobs bloat history files. → Optional truncation in UI display only; store full text for now.

## Migration Plan

Default all bots to reasoning off — no behavior change until user enables. Existing messages without `reasoning` field remain valid.

## Open Questions

- Should reasoning panel integrate with waiting-ui change (status 「正在思考…」 on first reasoning_token)? Recommended: yes during apply if both changes land.
