## Context

现有 spec 要求 learner 离线、只产候选。实现上只有 `collect_signal()` 落盘 JSON，无消费者。资料中 Skillify 闭环的第一步是 Nudge：在合适时机触发 Review Agent，而不是每轮都跑。

## Goals / Non-Goals

**Goals:**

- 轻量规则 + 可选 LLM 分类（默认规则-only，零额外模型成本）
- Trigger 类型：user_correction, multi_turn_revision, task_completion, topic_burst
- Review job 输出 structured candidate，status=pending
- 与 `learner_enabled` 联动；默认 false

**Non-Goals:**

- 自动 approve / 写 soul / 写 skill
- GEPA
- 每轮 LLM review

## Decisions

1. **Phase 1 规则引擎**：正则 + 轮次计数 + 用户消息关键词（「不对」「错了」「应该是」）。
2. **Review job**：批处理，消费 pending signals；可用 extraction 模型做 cheap summary。
3. **Candidate 类型**：先三类，skill_draft 为 `mnemos-skill-memory` 前置。
4. **Dedupe**：同 session 同 topic 24h 内只产一条同类 candidate。
5. **API**：`GET /api/bots/{id}/learner/candidates` 列出 pending（可选 UI 后续）。

## Risks / Trade-offs

- 误触发 → conservative 阈值 + dedupe
- 噪声 candidate → 人工 approve 流程（P6 完整闭环）
