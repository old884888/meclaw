## 1. Configuration

- [x] 1.1 Add `reasoning_enabled`, `reasoning_level`, `reasoning_visible` to bot config schema and config_store normalization
- [x] 1.2 Expose fields in bot editor API (`GET/PUT /api/bots/{id}`)
- [x] 1.3 Add settings UI controls (toggle + level select + visible toggle)

## 2. Provider Layer

- [x] 2.1 Add `resolve_reasoning_params(profile, bot, level)` mapping table
- [x] 2.2 Update `build_payload()` to use resolved params; remove unconditional DeepSeek thinking disabled when reasoning on
- [x] 2.3 Extend SSE parsers to yield `(kind, text)` for reasoning vs content (OpenAI `reasoning_content`, Anthropic thinking deltas)
- [x] 2.4 Update `stream_chat()` to yield typed chunks or add `stream_chat_with_reasoning()` wrapper

## 3. WebSocket & Persistence

- [x] 3.1 Emit `reasoning_token` events from `_run_generation` worker loop
- [x] 3.2 Extend `make_message()` / `_append_assistant_message` with optional `reasoning` field
- [x] 3.3 Ensure context builder excludes `reasoning` from prior assistant messages
- [x] 3.4 Ensure memory `after_turn` hooks use answer content only

## 4. Frontend Panel

- [x] 4.1 Handle `reasoning_token` in `handleWsEvent`; render collapsible `.msg-reasoning` block
- [x] 4.2 Persist reasoning in message render for historical messages
- [x] 4.3 Integrate with waiting UI: show 「正在思考…」 on first reasoning_token when panel visible

## 5. Tests & Validation

- [x] 5.1 Unit test: DeepSeek payload thinking enabled/disabled by bot setting
- [x] 5.2 Unit test: SSE parser extracts reasoning_content separately
- [x] 5.3 Manual test: enable reasoning on DeepSeek bot — panel streams then answer streams
- [x] 5.4 Verify next-turn prompt does not contain prior reasoning text
