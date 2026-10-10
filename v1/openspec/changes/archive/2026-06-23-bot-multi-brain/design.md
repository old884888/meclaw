## Context

- **现状**：`meclaw2/backend/main.py` 在 `_save_user_message_and_prepare()` 中组装 `system + user/assistant history`，未调用 `MemoryService`；`LayeredMemoryService` 偏向知识库 FTS 召回，且 `on_compress()` 为空实现。
- **用户目标**：个人对话极致优化——越聊越懂你、长聊不失忆、跨会话能接上；同时保留 SuperBrain 文档中的完整能力，但**分层激活**，避免每轮废 token、AI 绕弯子。
- **参考**：SuperBrain 三脑流水线、单调压缩边界、分级水位线、软删除；MNEMOS 已有 `MemoryService` Protocol、`history/` 会话存储、Bot/Soul 体系。
- **交付边界**：本变更聚焦 `meclaw2/`；1.0 可后续移植编排层，不在本阶段同步。

## Goals / Non-Goals

**Goals:**

- 每个 Bot 具备可配置的多脑子协作模型，默认启用「执行脑 + 记忆脑 + 右脑轻量人格」。
- 聊天主链路增加编排层：意图路由 → 按需召回 → 预算内组装 → 流式生成 → 异步写入/学习。
- 个人对话记忆 L0–L3 全链路：原始轮次、原子事实、会话摘要、用户画像。
- 上下文压力时分级压缩，最近 N token 保护区，替换决策单调可缓存。
- 每步有明确目的与 token 上限；未激活脑子零注入。

**Non-Goals:**

- 不以知识库/Wiki 导入作为本变更 MVP 验收项。
- 不引入 embedding 服务依赖（可用 FTS + 轻量关键词/规则召回）。
- 不让模型在每轮自行决定是否查记忆（避免绕路与额外推理 token）。
- 学习脑不自动生效画像或 prompt 变更。

---

## Multi-Brain Model

### 脑子分工

```text
                    ┌─────────────────────────────────────┐
                    │         用户输入 / WebSocket         │
                    └──────────────────┬──────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  执行脑 Executor（唯一对外）                                        │
│  - 加载会话、调用编排器、组装 messages、stream_chat、返回回复        │
│  - 只读各脑子输出块，不直接写 storage                               │
└───────────────┬──────────────────────────────────────────────────┘
                │
    ┌───────────┼───────────┬───────────────┐
    ▼           ▼           ▼               ▼
┌────────┐ ┌────────┐ ┌──────────┐   ┌────────────┐
│ 右脑   │ │ 记忆脑 │ │ 左脑     │   │ 学习脑     │
│ Persona│ │ Memory │ │ Cognitive│   │ Learner    │
│ 必开   │ │ 必开   │ │ 按需     │   │ 仅后台     │
│ 轻量   │ │ 读写压 │ │ 零默认   │   │ 零实时     │
└────────┘ └────────┘ └──────────┘   └────────────┘
```

| 脑子 | 代号 | 实时默认 | 职责 | Token 策略 |
|------|------|----------|------|------------|
| 执行脑 | `executor` | 是 | 编排、组 prompt、调 API | 不单独占块，承载输出 |
| 右脑 | `persona` | 是 | Soul 摘要 + L3 画像短句 + 语气约束 | 硬上限 ~300–500 |
| 记忆脑 | `memory` | 是 | L1 召回、L2 会话摘要、压缩 | 硬上限 `memory_token_budget` |
| 左脑 | `cognitive` | 否 | 任务结构、约束核对、逻辑清单 | 命中时 ~200–400，否则 0 |
| 学习脑 | `learner` | 否 | 信号收集、画像候选、离线聚合 | 实时 0 |

### 右脑 vs 左脑（用户隐喻落地）

- **右脑（Persona）**：「像不像这个 Bot、懂不懂用户情绪与关系」——来自 `soul.md`、constraints、L3 用户画像的**预压缩短摘要**，每轮固定注入一小块，不让模型重写人格。
- **左脑（Cognitive）**：「事情有没有理清、约束有没有漏」——当用户消息命中规划/实现/对比/步骤类意图时，注入结构化提示（待办框、约束清单、上一步结论），**不**默认开启。

---

## Turn Pipeline（每轮必有意义的步骤）

```text
1. ingest      保存 user message 到 history（已有）
2. route       规则意图路由（零 LLM）：要不要左脑？要不要跨会话？要不要深召回？
3. persona     右脑块 = soul 摘要 + L3 短画像（有预算截断）
4. recall      记忆脑 before_chat：L2 当前会话摘要 + L1 top-k + 可选跨会话 L2
5. compact     若 context_ratio >= tier1：记忆脑 compact（同步，压完再发）
6. assemble    stable 顺序：system(soul) → persona → memory → cognitive? → session_summary → history
7. generate    stream_chat
8. persist     写 assistant message
9. async       after_turn → L0；队列 L1 提取；collect_signal → 学习脑
```

**原则**：步骤 2–6 每步输出可见、可测、有 token 计量；步骤 9 不阻塞 WebSocket。

---

## Personal Memory Pyramid（记忆脑内部）

| 层 | 名称 | 内容 | 存储 | 进 prompt 时机 |
|----|------|------|------|----------------|
| L0 | 原始轮次 | user/assistant 原文、工具输出引用 | `memory/l0/*.json` | 仅追溯/管理，默认不进 |
| L1 | 原子记忆 | fact/preference/constraint/todo | `memory/l1/*.md` + index | 召回 top-k |
| L2 | 会话摘要 | 进展/待办/关键决策 | `history/summaries/` + `memory/l2/` | 当前会话必带短摘要 |
| L3 | 用户画像 | 长期偏好、项目、关系 | `memory/l3/user_profile.md` | 右脑块内嵌短句 |

追溯链：`L3 → L2 → L1 → L0`，任意摘要可回到证据。

---

## Context Compaction（记忆脑子模块）

沿用 SuperBrain 四级水位线，阈值相对 `max_context` 动态计算：

| Tier | 阈值 | 动作 | LLM 成本 |
|------|------|------|----------|
| 0 | < 60% | 无 | 0 |
| 1 | ≥ 60% | Snip 工具输出/长代码块 | 0 |
| 2 | ≥ 80% | Prune 占位替换 + replacement_cache | 0 |
| 3 | ≥ 95% | 增量 running summary | 1 次 |

- **保护区**：最近 `protection_zone_tokens`（默认 8000 或按模型比例）不压。
- **单调边界**：`replacement_cache` 记录 part_id 决策，已替换永不恢复，利于 Prompt Cache 稳定。

---

## Intent Router（防绕路、省 token）

**规则优先，不先问 LLM「你要查什么记忆」**。

| 信号 | 激活 |
|------|------|
| 默认每轮 | 右脑 + 记忆脑轻召回（L3 短句 + L2 当前会话 + L1 top-3） |
| 「继续/上次/之前/我们说过」 | 跨会话 L2 召回 |
| 「步骤/实现/对比/为什么/计划」 | 左脑块 |
| 「原文/当时怎么说的/引用」 | L0 深召回（仍受预算限制） |
| 上下文 ratio ≥ 0.6 | 压缩引擎 |

路由实现：`meclaw2/backend/domain/brains/router.py`，纯 Python 规则 + 可选关键词表，**零 token**。

---

## Data Layout

```text
meclaw2/data/
  history/
    sessions.json
    {session_id}.json
    summaries/{session_id}_summary.md    # L2 当前会话
  memory/
    l0/{session_id}_{ts}.json            # 对话证据
    l1/{date}-{slug}.md                  # 原子记忆
    l2/{session_id}.md                   # 跨会话可检索的会话块（可选）
    l3/user_profile.md                   # 用户画像
    index.sqlite                         # FTS：L1/L2 检索
    replacement_cache/{session_id}.json  # 压缩决策
    deleted/                             # 软删除审计（JSONL）
  souls/{bot_id}/
    soul.md
    constraints.md
```

文件为真源，SQLite 为检索加速；与 MeClaw 1.0「文件夹 + FTS」哲学一致，但目录挂在 `data/memory/` 而非 bot 级 knowledge。

---

## Module Structure

```text
meclaw2/backend/domain/
  brains/
    orchestrator.py      # 编排入口：route → gather blocks → assemble
    router.py            # 意图路由
    persona_brain.py     # 右脑
    cognitive_brain.py   # 左脑
    learner_brain.py     # 学习脑（调度 + collect_signal）
    budgets.py           # Token 预算与计量
  memory/
    protocol.py          # MemoryService（保持）
    memory_brain.py      # 记忆脑门面：recall / store_turn / compact
    compaction.py        # 四级压缩引擎
    store_l0.py / store_l1.py / ...
    indexer.py           # memory index.sqlite FTS
    layered.py           # 逐步废弃或委托 memory_brain
```

`main.py` 改动点：

- `_save_user_message_and_prepare()` 调用 `Orchestrator.prepare_turn()` 替代手写 `api_messages`。
- `_run_generation()` 完成后 `asyncio.create_task` 调度 `after_turn` 与 `learner.collect_signal`。

---

## Configuration

```json
{
  "multi_brain_enabled": true,
  "brains": {
    "persona_enabled": true,
    "memory_enabled": true,
    "cognitive_enabled": true,
    "learner_enabled": true
  },
  "memory_token_budget": 800,
  "persona_token_budget": 400,
  "cognitive_token_budget": 300,
  "protection_zone_tokens": 8000,
  "compaction_tier1_pct": 60,
  "compaction_tier2_pct": 80,
  "compaction_tier3_pct": 95,
  "l1_extract_every_turn": true,
  "l2_update_every_n_turns": 5,
  "l3_update_every_n_turns": 20,
  "learner_schedule": "0 3 * * *"
}
```

---

## API / UX Sketch

- **透明模式（可选）**：WebSocket 在 `send` 后推送 `brain_trace` 事件：`{activated: ["persona","memory"], tokens: {persona: 120, memory: 450}, compact_tier: 0}`，便于调试，默认关闭。
- **记忆面板（P2）**：列表 L1/L3、软删除、查看 L0 证据链。
- **学习脑候选（P3）**：`prompt_candidates.json` 待用户批准。

---

## Risks

| Risk | Mitigation |
|------|------------|
| 每轮 LLM 提取 L1 费 token/慢 | 可配置 `l1_extract_every_turn`；默认异步批处理 |
| 压缩阻塞首 token | 仅高水位同步；Tier1/2 零 LLM |
| 与旧 LayeredMemoryService 冲突 | memory_brain 统一门面，layered 委托或废弃 |
| 多脑子概念用户难理解 | UI 用「人格 / 记忆 / 思考 / 学习」中文标签，技术名仅日志 |
| 跨会话召回误命中 | 路由加 session 边界 + 相似度阈值 + top-k 限制 |

---

## Phased Delivery

```text
Phase A — 接线与编排
  Orchestrator + Router + 右脑 + 执行脑挂载 main.py

Phase B — 记忆脑 MVP
  L0 写入、L1 提取、L2 会话摘要、before_chat 召回、index.sqlite

Phase C — 压缩引擎
  Tier1–3、replacement_cache、保护区

Phase D — 左脑按需 + 跨会话召回

Phase E — 学习脑离线 + 记忆面板 + brain_trace UI
```

---

## Open Questions

- 记忆作用域：全局 `data/memory/` 还是 per-bot `souls/{id}/memory/`？**建议 Phase A 用 per-bot**，与 Soul 人格一致；全局画像可作为 L3 扩展。
- L1 提取模型：复用 Bot 绑定供应商还是独立便宜模型？**建议复用 Bot profile，异步且可配置 max_tokens**。
- 是否保留 `knowledge/` 并行：**保留代码，默认不进个人对话编排器**，避免双轨抢预算。
