## Context

- **已完成**：`archive/2026-06-23-bot-multi-brain/` — 全局多脑子编排、记忆 L0–L3、Tier1–3 压缩、设置页「多脑子」Tab。
- **缺口**：编排策略全局一份；Tier3/L1 与主对话共用 `bot.model`；陪聊 Bot 与编程 Bot 无法差异化。
- **用户诉求**：多脑子进每个 Bot；不同任务可用不同模型，但不要过度复杂。

## Goals / Non-Goals

**Goals:**

- Bot 级 `brains` 覆盖全局默认。
- Bot 级 `background_model` 用于后台 LLM（摘要、L1、学习脑候选）。
- Bot 编辑弹窗可配置；全局设置作为默认模板。
- 配置合并可预测、可测试。

**Non-Goals:**

- 五脑五模型。
- 跨 Bot 共享 L3 用户画像（后续独立变更）。
- 删除全局多脑子 Tab（改为「默认值」）。

---

## Configuration Model

```json
{
  "multi_brain_enabled": true,
  "brains": { "persona_enabled": true, "memory_enabled": true, ... },
  "memory_token_budget": 800,
  "bots": [
    {
      "id": "b_xxx",
      "name": "陪聊",
      "profile_id": "p_xxx",
      "model": "gpt-4o",
      "background_model": "gpt-4o-mini",
      "brains": {
        "persona_enabled": true,
        "memory_enabled": true,
        "cognitive_enabled": false,
        "learner_enabled": false,
        "memory_token_budget": 600,
        "persona_token_budget": 500
      }
    }
  ]
}
```

### Merge Rule

```text
effective = { **global_brain_defaults, **bot.brains }
```

- Bot 未设置 `brains` → 100% 全局。
- Bot 只设置部分字段 → 其余继承全局。
- `multi_brain_enabled` 仍为全局总开关；Bot 可设 `brains.enabled: false` 关闭该 Bot 的多脑子（可选，P1）。

### Model Resolution

```text
executor_model  = bot.model || profile.default_model
background_model = bot.background_model || bot.model || profile.default_model
```

| 任务 | 模型 |
|------|------|
| 主对话 stream_chat | executor_model |
| Tier3 增量摘要 | background_model |
| L1 原子记忆提取 | background_model |
| 学习脑候选生成（未来） | background_model |
| 意图路由 / FTS 召回 | 无 LLM |

---

## UI

### Bot 编辑弹窗 — 新增「多脑子」折叠区

- 继承提示：「未填写项使用设置 → 多脑子默认值」
- 开关：右脑 / 记忆 / 左脑 / 学习
- 数字：记忆 / 人格 / 左脑 token 预算（可留空=继承）
- 下拉：**后台模型**（同供应商模型列表；空=与主模型相同）

### 全局设置 — 「多脑子」Tab

- 标题改为「多脑子默认值」
- 说明：影响所有未单独配置的 Bot

---

## Backend Changes

1. `normalize_bot()` 增加 `background_model`, `brains` 可选对象。
2. `brains_config_for_bot(cfg, bot) -> dict` 合并 helper。
3. `orchestrator` / `memory_brain` 接收 `effective_brains` 而非只读全局。
4. `_profile_for_bot(bot, *, role="executor"|"background")` 设置 `merged["model"]` 为对应模型。
5. Bot PUT/POST API 接受并持久化新字段。

---

## Migration

- 旧 `config.json` 无 `bots[].brains` → 行为与现在一致。
- 旧 Bot 无 `background_model` → 后台任务继续用主模型（与现况相同）。

---

## Risks

| Risk | Mitigation |
|------|------------|
| 配置分散难找 | Bot 编辑集中；全局 Tab 标明「默认」 |
| background 模型与 executor 不同供应商 | P0 限制为同 profile 内选模型 |
| 合并逻辑 bug | 单元测试 `brains_config_for_bot` |
