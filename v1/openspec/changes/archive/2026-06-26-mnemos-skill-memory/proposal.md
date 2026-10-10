## Why

L1 擅长存「是什么」，不擅长存「怎么做」。Hermes Skillify 的核心是把执行轨迹沉淀为可复用 SKILL.md，渐进加载。我们记忆检索已强于资料中的 Session Search，但缺少 Skill 温数据层，learner 的 `skill_draft` 候选无处落地。本提案引入 per-bot Skill 资产层，与 L1 并列、按需召回。

## What Changes

- 存储：`souls/<bot>/skills/` 下结构化 skill 文件 + index
- Schema：title, when_to_use, steps, pitfalls, examples, status, superseded_by
- 召回：任务型 query 时 hybrid 检索 skill top-k，注入动态块（非 stable system）
- 渐进加载：默认不注入；命中 score > 阈值才加载单个 skill body
- 生命周期：pending → approved → archived；仅 approved 参与召回
- 与 learner：`skill_draft` candidate approve 后写入 skill 目录

## Capabilities

### New Capabilities

- `mnemos-skill-memory`: Per-bot procedural skill storage, retrieval, and progressive injection.

### Modified Capabilities

- `mnemos-multi-brain-orchestrator`: MAY inject approved skills into dynamic blocks when task intent is detected.

## Impact

- 后端：新 `skill/` 模块、orchestrator 动态块、embedding 索引复用
- 前端（可选）：Skill 管理 UI、candidate approve
- 验证：任务重复场景复用率；token 注入量不超标
