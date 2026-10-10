## 1. Storage & schema

- [x] 1.1 Add `skills/` layout under bot soul dir + frontmatter schema
- [x] 1.2 Skill index table (embedding, status, tags) reusing embedding port
- [x] 1.3 CRUD helpers: create, approve, archive, supersede

## 2. Recall & injection

- [x] 2.1 Task intent detection hook (rule-based MVP)
- [x] 2.2 Hybrid skill search + optional rerank
- [x] 2.3 Inject `[相关技能]` dynamic block in orchestrator with `skill_token_budget`
- [x] 2.4 Config: `skill_recall_enabled`, budget, top-k, threshold

## 3. Learner integration

- [x] 3.1 Approve API: `POST /api/bots/{id}/learner/candidates/{id}/approve` → write skill
- [x] 3.2 Reject/archive candidate endpoints
- [x] 3.3 Link from `mnemos-learner-nudge-trigger` skill_draft type

## 4. Tests & docs

- [x] 4.1 Unit tests: approved-only injection, budget cap, supersede exclusion
- [ ] 4.2 Smoke: repeat task reuses same skill without full L1 dump
- [x] 4.3 Update 超级大脑增强路线.md cross-reference (optional)
