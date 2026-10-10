## 1. Context assembler (2.0)

- [x] 1.1 Add `meclaw2/backend/domain/brains/context_assembler.py` with `join_blocks`, `build_dynamic_context`, `prefix_user_content`, `assemble_api_messages` (port of 1.0 logic).
- [x] 1.2 Document the fixed assembly order (`stable → semi_stable → history → dynamic tail`) as a cache-matching constraint in module docstring.
- [x] 1.3 Add unit tests: dynamic prefixes last user message; no-user appends a user message; multimodal text-part prefixing. → `meclaw2/tests/test_context_assembler.py` (16 tests)

## 2. Wire orchestrator to assembler

- [x] 2.1 Refactor `MultiBrainOrchestrator.prepare_turn()` to collect stable (system_base + persona), semi_stable (reserved/empty), and dynamic (memory + cognitive + session summary + time) blocks.
- [x] 2.2 Replace direct system-message appends for memory/cognitive/summary with dynamic-tail injection via the assembler.
- [x] 2.3 Preserve `brain_trace` `activated` / `tokens` accounting (token counts unchanged; only message position changes).
- [x] 2.4 Remove the pre-history `[会话摘要]` system message; route summary through the dynamic layer instead.
- [x] 2.5 Add unit test asserting stable system content contains no query-derived memory/cognitive/summary/timestamp text. → `test_orchestrator_stable_prefix_no_dynamic_content` in smoke tests

## 3. Deterministic payload serialization

- [x] 3.1 In `providers.py`, serialize payload with `json.dumps(..., ensure_ascii=False, sort_keys=True)` and POST as data for generic/deepseek/anthropic branches. → `_post_json()` helper
- [x] 3.2 Verify existing streaming and `chat_once` still parse responses correctly after the serialization change. → all smoke tests pass

## 4. Cache usage parsing

- [x] 4.1 Extend SSE parsing to capture provider `usage` (OpenAI/DeepSeek end chunk; Anthropic `message_start`/`message_delta`). → `_parse_openai_sse_line` / `_parse_anthropic_sse_line` updated with `usage_collector`
- [x] 4.2 Add a helper computing `{ read, create, hit_rate, supported }` from `cache_read_input_tokens`/`prompt_cache_hit_tokens` and `cache_creation_input_tokens`/`prompt_cache_miss_tokens`. → `parse_cache_usage()`
- [x] 4.3 Surface parsed usage from `stream_chat()` without breaking the text-token yield contract (collector dict or optional callback). → `usage_collector: dict | None` optional param
- [x] 4.4 Return `supported = false` (no error) when no cache fields are present.
- [x] 4.5 Add unit tests for DeepSeek-style, Anthropic-style, and field-absent usage payloads. → `meclaw2/tests/test_cache_usage.py` (13 tests)

## 5. WebSocket + status API

- [x] 5.1 In `main.py` generation flow, emit `{ event: "cache_usage", generation_id, read, create, hit_rate, supported }` at stream completion.
- [x] 5.2 Store latest cache metrics per session in best-effort runtime state (reset-safe across restarts). → `save_session_cache_usage` / `get_session_cache_usage` in `runtime_status.py`
- [x] 5.3 Extend `brain_status.py` `context` section with a `cache` subobject (`read`, `create`, `hit_rate`, `supported`, `updated_at`).

## 6. Frontend display

- [x] 6.1 Add `state.lastCacheUsageBySession`; handle WebSocket `cache_usage` events.
- [x] 6.2 Extend `updateUsageHint()` to append `缓存命中 X%` when supported; omit/placeholder when unsupported.
- [x] 6.3 Render cache read/create/hit_rate in the detail panel Context section via `renderBsCacheSection()`; show "供应商不支持缓存指标" when unsupported.
- [x] 6.4 Add minimal styles in `style.css` (`.bs-cache-row`, `.bs-cache-ok/warn/neutral`).

## 7. cache-safe compaction review

- [x] 7.1 Audit `compact_for_api()` / `compaction.py` to confirm the stable system prefix is never rewritten. → Confirmed: `tier1_snip` / `tier2_prune` pass system role unchanged; Tier 3 creates new summary message, does not mutate existing system.
- [x] 7.2 If any path mutates system prefix, adjust to only touch history/dynamic/summary. → No adjustment needed.

## 8. Tests and verification

- [x] 8.1 Run `py -3 meclaw2/tests/test_multi_brain_smoke.py`. → OK (12 tests including new stable-prefix assertion)
- [x] 8.2 Run `python -m compileall meclaw2/backend`. → OK (no errors)
- [x] 8.3 Extend multi-brain smoke for assembly order + dynamic-tail injection. → `test_orchestrator_stable_prefix_no_dynamic_content` added

## 9. Manual acceptance

- [x] 9.1 Chat with a DeepSeek profile across multiple turns; composer shows a rising cache hit rate.
- [x] 9.2 Open the status detail panel; Context section shows cache read/create/hit_rate.
- [x] 9.3 Use a provider without cache fields; UI shows unsupported state, no error.
- [x] 9.4 Confirm reply content is unchanged versus pre-change behavior (position-only refactor).
