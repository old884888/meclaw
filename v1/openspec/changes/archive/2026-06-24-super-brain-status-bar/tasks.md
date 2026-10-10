## 1. Backend status API

- [ ] 1.1 Add `GET /api/bots/{bot_id}/brain/status?session_id=` in `meclaw2/backend/main.py`.
- [ ] 1.2 Add `brain_status_for_bot(bot_id, session_id=None)` helper that returns health, bot, brains, memory, context, background_jobs, and turn_trace sections.
- [ ] 1.3 Reuse `_public_bot()`, `brains_config_for_bot()`, and `_profile_for_bot(..., role=...)` so status matches actual chat behavior.
- [ ] 1.4 Ensure missing Bot returns 404, while missing memory/session data returns a valid status with empty values.

## 2. Memory stats

- [ ] 2.1 Add `memory_stats_for_bot(souls_dir, history_dir, sessions_index_path, bot_id)` helper.
- [ ] 2.2 Count L0 evidence, L1 atoms, L2 summaries, and L3 profile availability without loading large bodies.
- [ ] 2.3 Return `index_status` as `ready | missing | error`.
- [ ] 2.4 Return best-effort `last_write_at` from L0 metadata or file mtime.
- [ ] 2.5 Add smoke tests for missing memory directory, populated L1/L3, and index existence.

## 3. Trace schema stabilization

- [ ] 3.1 Extend `MultiBrainOrchestrator.prepare_turn()` trace with stable default keys for all brain blocks.
- [ ] 3.2 Add `memory` trace subsection with recall count, cross-session flag, and L0 deep recall flag when available.
- [ ] 3.3 Add model labels to trace or status response: executor and background.
- [ ] 3.4 Keep `brain_trace_enabled` default false, but store latest trace server-side for status API when practical.
- [ ] 3.5 Add tests asserting trace has `activated`, `tokens`, `compact_tier`, `context_ratio`, and default-safe optional sections.

## 4. Background job status

- [ ] 4.1 Add lightweight runtime status store for L1 extraction, Tier3 summary, and learner signal collection.
- [ ] 4.2 Mark status `running/success/failed/idle/disabled` around existing post-turn hooks.
- [ ] 4.3 Include model, last run time, created count, and last error when available.
- [ ] 4.4 Keep status best-effort and reset-safe across process restarts.

## 5. Frontend state and loading

- [ ] 5.1 Add `state.brainStatus`, `state.brainStatusLoading`, and `state.lastBrainTraceBySession`.
- [ ] 5.2 Add `loadBrainStatus({ silent })` to call `/api/bots/{bot_id}/brain/status`.
- [ ] 5.3 Trigger status loading after bootstrap, entering Bot, switching/new session, Bot save, settings save, and generation completion.
- [ ] 5.4 Merge incoming WebSocket `brain_trace` events into status state without requiring a full reload.

## 6. Topbar capsule UI

- [ ] 6.1 Add a topbar `超级大脑状态` capsule between `说明书` and `设置`.
- [ ] 6.2 Render idle, ok, warn, and error styles.
- [ ] 6.3 Capsule label should summarize health, memory recall count, context ratio, and background state.
- [ ] 6.4 Clicking capsule opens the detail panel.

## 7. Composer light status

- [ ] 7.1 Extend existing `#usage-hint` rendering to include context ratio, compact tier, recall count, and background state.
- [ ] 7.2 Preserve existing message count behavior.
- [ ] 7.3 Show neutral text when no session or no trace exists.

## 8. Detail panel UI

- [ ] 8.1 Add a status modal/sheet with sections: Current Bot, Brains, Memory, Context, Background Jobs, Turn Trace.
- [ ] 8.2 Render five brain dots/cards: Executor, Persona, Memory, Cognitive, Learner.
- [ ] 8.3 Render memory L0/L1/L2/L3 stats and index state.
- [ ] 8.4 Render context token estimate, max context, ratio, compact tier, protection zone, and summary active state.
- [ ] 8.5 Render background job states for L1 extraction, Tier3 summary, and Learner.
- [ ] 8.6 Provide empty states for no Bot, no session, memory disabled, and no trace.

## 9. Styling and usability

- [ ] 9.1 Add capsule styles with compact responsive behavior.
- [ ] 9.2 Add status colors for ok/warn/error/idle.
- [ ] 9.3 Add brain dot styles for active/inactive/disabled/warn/error.
- [ ] 9.4 Ensure status panel scrolls independently and does not block chat layout after close.

## 10. Tests and verification

- [ ] 10.1 Add backend smoke test for `/api/bots/{bot_id}/brain/status`.
- [ ] 10.2 Add memory stats unit tests.
- [ ] 10.3 Extend multi-brain smoke tests for trace schema.
- [ ] 10.4 Run `py -3 meclaw2/tests/test_multi_brain_smoke.py`.
- [ ] 10.5 Run compile/lint checks for changed backend/frontend files.

## 11. Manual acceptance

- [ ] 11.1 Open MNEMOS home: topbar capsule shows idle.
- [ ] 11.2 Enter a chat-ready Bot: capsule shows ok state and model/memory context.
- [ ] 11.3 Send a message: `brain_trace` updates composer and detail panel.
- [ ] 11.4 Disable memory globally or per Bot: status panel reflects disabled memory.
- [ ] 11.5 Configure Bot `background_model`: status panel shows executor/background model split.
- [ ] 11.6 Force long context or low threshold: compact tier updates visibly.
- [ ] 11.7 Break provider config: status shows error without crashing UI.
