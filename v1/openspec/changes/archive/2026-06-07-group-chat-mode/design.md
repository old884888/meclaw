## Context

- 私聊：1 Bot : N sessions，`bot_id` 绑定，`souls/{id}/memory/` 跨 session 共享。
- 群聊：N Bots : 1 group : M sessions；需避免多 Bot 同时抢答与记忆串库。

## Goals / Non-Goals

**Goals:**

- 群聊 Tab + 群列表 → 群 session 列表（导航结构镜像私聊 Bot 层）
- @ 指定单 Bot 回复
- `groups/{id}/memory/` 群级检索；私聊记忆路径不变
- 设置：记忆整理代理（Bot 或 API）

**Non-Goals:**

- 未 @ 时全员自动回复
- 群记忆自动同步进各 Bot 私聊 memory（除非未来显式产品决策）
- Phase 1 群聊与私聊导航同一迭代发布

## Decisions

### 1. 群数据模型（草案）

```text
groups/
  groups.json                 # 索引
  {group-id}/
    meta.json                 # name, avatar, member_bot_ids[], created_at
    memory/                   # 同 souls/{id}/memory/ 结构（items + index.sqlite）
    # sessions 二选一：
    # A) history 共用，session 增 group_id + member_bot_ids
    # B) groups/{id}/sessions.json 独立索引
```

**✅ Q8-A — 已确认**：复用 `history.py`，session 增加：

```json
{
  "id": "...",
  "group_id": "grp_xxx",
  "bot_id": "",
  "member_bot_ids": ["bot_a", "bot_b"],
  "title": "群对话一"
}
```

私聊 session：`group_id` 空，`bot_id` 非空。互斥。

### 2. @ 指定回复

- 用户消息解析 `@Bot名` 或 UI 选择 @ 成员 → `target_bot_id`
- 仅 `target_bot_id` 进入 `build_messages_for_api`（单人设 + 可选群记忆检索）
- **✅ Q6-B**：未 @ 时**允许发送**，但不触发任何 Bot 回复（无禁发、无系统拦截）

### 3. 记忆隔离

| 场景 | 检索范围 | 写入范围 |
|------|----------|----------|
| 私聊 session | `souls/{bot_id}/memory/` | 同上 |
| 群聊 session | `groups/{group_id}/memory/` | 同上（压缩提取写群库） |
| 用户私聊中「问我记得什么」 | 仅当前 Bot 私聊库 | — |

各 Bot 的 `soul.md` / 人设仍在被 @ 回复时注入；**不**把群记忆默认 merge 进 Bot 私库。

### 4. 记忆整理代理（设置，✅ Q7-C）

全局配置：

```json
{
  "memory_organizer_enabled": false,
  "memory_organizer_profile_id": "",
  "memory_organizer_bot_id": ""
}
```

- **Profile（主）**：启用后压缩/记忆提取的 **LLM 调用必须走** `memory_organizer_profile_id`
- **Bot（辅）**：`memory_organizer_bot_id` **仅**用于整理任务的 system 人设（加载该 Bot 的 `soul.md`），不替代 API 端点
- 整理范围：私聊写 Bot 库；群聊写群库（按当前 session 类型）

### 5. 侧边栏 Tab

```text
[💬 对话]  [👥 群聊]
```

- 对话 Tab：Bot 列表（`bot-centric-navigation`）
- 群聊 Tab：群列表 → 群 session 列表
- 私聊改版第一版（Q5-A）：群聊 Tab **灰色占位**「即将推出」；群聊功能上线后激活

### 6. @ 交互形态（✅ Q0.4-A）

- 输入框支持 **@ 弹出群成员列表**（点击或输入 `@` 触发）
- 用户从列表选择成员，避免手写 `@Bot名` 与重名歧义
- 选中后在输入区插入可解析的 mention 标记（实现细节：chip 或 `@Bot名` 文本 + `target_bot_id` 元数据）

## 已关闭决策（2026-06-05）

| 问题 | 答案 |
|------|------|
| Q5 群聊 Tab（Phase 1） | A — 灰色占位 |
| Q6 未 @ 行为 | B — 可发送，无 Bot 回复 |
| Q7 整理代理 | C — API 负责调用；Bot 仅影响 system 人设 |
| Q8 群 session 存储 | A — 复用 `history/` + `group_id` |
| Q0.4 @ 交互 | A — 输入框 @ 成员选择器 |

## Phase 2 — Bot 自动接话（见 `group-auto-interaction`）

Phase 1 已落地。Phase 2 决策（2026-06-06）：

| 项 | 决策 |
|----|------|
| @ 谁 | 模型在提示词里选 |
| 多 @ | 串行回复 |
| @ 生成 | 混合（模型 + `auto_mention_pct` 补 @） |
| @用户 | 纯装饰 |

提案路径：`openspec/changes/group-auto-interaction/`

## Risks

- @ 解析与 Bot 重名
- 群 session 压缩提取写入群库后，被 @ Bot 私聊检索不到群内容（符合隔离设计，需在帮助文档说明）
- Phase 2 Bot 接话链可能增加 API 成本（见 group-auto-interaction 轮次上限）
