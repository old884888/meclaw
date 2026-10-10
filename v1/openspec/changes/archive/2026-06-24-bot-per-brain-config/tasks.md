## 1. Config schema and merge helpers

- [ ] 1.1 Extend `normalize_bot()` with optional `background_model` and `brains` object.
- [ ] 1.2 Add `brains_defaults(cfg)` and `brains_config_for_bot(cfg, bot)` merge helper with tests.
- [ ] 1.3 Add `_profile_for_bot(bot, role="executor"|"background")` model resolution in `main.py`.

## 2. Wire effective config through orchestrator

- [ ] 2.1 Pass `effective_brains` from bot merge into `MultiBrainOrchestrator.prepare_turn()`.
- [ ] 2.2 Update `MemoryBrain` to read per-bot budgets when present in merged config.
- [ ] 2.3 Use background profile for `tier3_summarizer` and `l1_extractor` LLM calls.

## 3. Bot API and persistence

- [ ] 3.1 Accept `background_model` and `brains` in Bot POST/PUT APIs.
- [ ] 3.2 Return merged effective brains summary in `GET /api/bots/{id}` for editor display (optional `effective_brains` field).

## 4. Bot editor UI

- [ ] 4.1 Add collapsible「多脑子」section in bot editor modal.
- [ ] 4.2 Brain toggles + budget inputs with empty=inherit placeholders.
- [ ] 4.3 Background model dropdown (same provider model list as main model).
- [ ] 4.4 Save/load via bot update API.

## 5. Global settings copy update

- [ ] 5.1 Rename global tab intro to「多脑子默认值」.
- [ ] 5.2 Clarify that per-bot settings override these defaults.

## 6. Tests

- [ ] 6.1 Unit tests: config merge, model resolution executor vs background.
- [ ] 6.2 Smoke test: bot with `background_model` uses it for L1 path (mock/no key fallback).
