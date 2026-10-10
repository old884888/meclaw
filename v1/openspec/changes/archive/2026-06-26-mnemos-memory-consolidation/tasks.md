## 1. Consolidation engine

- [x] 1.1 Add `consolidation/` module with merge, compress, archive actions
- [x] 1.2 Config: `memory_consolidation_enabled`, L3/topic/L2 capacity thresholds
- [x] 1.3 Pin rules: constraint type, high importance exempt from archive

## 2. Triggers & jobs

- [x] 2.1 Post-turn capacity check (async, non-blocking)
- [ ] 2.2 Scheduled fallback job when `learner_schedule` or dedicated cron fires
- [x] 2.3 Audit log: merge/archive events in bot memory dir

## 3. L3 & L2 integration

- [x] 3.1 L3 profile compression via summary role when over threshold
- [x] 3.2 Topic chain compress → summary node linked in metadata
- [x] 3.3 Exclude archived atoms from hybrid recall injection

## 4. Tests

- [x] 4.1 Unit tests: merge similar, archive low-value, pin protection
- [ ] 4.2 Long-session smoke: atom count stable after consolidation
- [x] 4.3 Brain status shows last consolidation run
