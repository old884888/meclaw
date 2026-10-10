## 1. L3 Profile Storage

- [x] 1.1 Confirm or add bot-scoped L3 profile paths under the existing memory layout.
- [x] 1.2 Implement heuristic L3 aggregation from L1 atoms grouped by type/topic/recency.
- [x] 1.3 Include source/session references or metadata for traceability.
- [x] 1.4 Preserve older conflicting L1 evidence while marking newer preferences as active in the profile summary.

## 2. Profile Generation Triggers

- [x] 2.1 Add initial profile generation when L1/L2 memory exists and L3 is missing.
- [x] 2.2 Add refresh behavior based on `l3_update_every_n_atoms` or an explicit refresh call (`force=True`).
- [x] 2.3 Ensure profile refresh failure does not block chat completion.
- [x] 2.4 Keep generated profile content separate from `soul.md`.

## 3. Prompt Injection

- [x] 3.1 Bounded L3 excerpt loading for Persona brain prompt contribution.
- [x] 3.2 `persona_token_budget` enforced via `read_profile_excerpt`.
- [x] 3.3 Prioritize durable preferences, constraints, style preferences (section ordering in profile).
- [x] 3.4 L3 status visible in brain trace (persona block includes profile excerpt when non-empty).

## 4. Tests

- [x] 4.1 Smoke tests for L3 profile generation from L1 preferences and constraints.
- [x] 4.2 Test for preference evolution where newer preference wins in injected profile.
- [x] 4.3 PersonaMem Lite dry-run after L3 injection enabled — storage/retrieval still 100%.
- [x] 4.4 Existing memory and multi-brain smoke tests still pass.

## 5. Documentation

- [x] 5.1 Document L3 profile file location and purpose.
- [x] 5.2 Document that L3 is generated memory and does not modify Soul files.
- [x] 5.3 Add notes on when to regenerate L3 and how to inspect or remove it.

### Validation notes (2026-06-24)

**Implementation:**
- `meclaw2/backend/domain/memory/profile_aggregator.py` — heuristic aggregation from L1 atoms
- Trigger: `memory_brain.py` `after_turn` (every `l3_update_every_n_atoms` atoms, default 5) and `rebuild_bot_index` (force=True)
- Injection: `persona_brain.py` already calls `read_profile_excerpt()` → `[用户画像]` block in system prompt
- Rollback: set `l3_profile_enabled: false` in config, or delete `memory/l3/user_profile.md`

**Profile file location:** `souls/<bot_id>/memory/l3/user_profile.md`  
This is generated content — L1/L0 evidence remains intact regardless.

**Tests (6/6 pass):** `meclaw2/tests/test_l3_persona_profile.py`  
All smoke tests and PersonaMem Lite benchmark continue to pass.
