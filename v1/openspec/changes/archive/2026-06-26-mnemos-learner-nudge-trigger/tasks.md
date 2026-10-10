## 1. Signal classification

- [x] 1.1 Add `nudge/` module with trigger rules (correction, multi-turn, task_done, topic_burst)
- [x] 1.2 Config: `learner_nudge_enabled`, thresholds, dedupe window
- [x] 1.3 Hook post-turn: classify signal after `collect_signal`

## 2. Review job

- [x] 2.1 Implement review job queue (file-based or in-memory + persist)
- [x] 2.2 Review produces candidates via extraction role (optional) or template
- [x] 2.3 Candidate schema: type, content, reason, bot_id, status, source_session

## 3. API & status

- [x] 3.1 `GET /api/bots/{bot_id}/learner/candidates?status=pending`
- [x] 3.2 Brain status: learner last run, pending candidate count
- [x] 3.3 Unit tests: trigger match, dedupe, no block on chat done

## 4. Integration prep

- [x] 4.1 Document handoff to `mnemos-skill-memory` for `skill_draft` approval flow
