## Context

- **Phase 1 已实现**：用户 `mention_bot_ids` → 串行 `send_message` / `send_group_bot_reply`；群环境 system 块；未 @ 仅存档。
- **缺口**：Assistant 消息里的 `@Bot` 不触发任何人；无 Bot 互聊；无概率控制。

## Goals / Non-Goals

**Goals:**

- Bot 可在回复中 @ 其他 Bot 或 @用户（模型选择对象）
- 解析 Bot 消息中的 `@Bot` → 按 `auto_reply_pct` 决定是否接话
- 群级 `auto_interaction_enabled` + 每 Bot `auto_mention_pct` / `auto_reply_pct`
- 混合 mention：模型正文 + 概率后处理补 @
- 串行接话，轮次上限

**Non-Goals:**

- `@用户` 触发 API 或通知
- 并行多 Bot 同时流式
- 接话写入各 Bot 私聊 memory（仍只写群库）

## Decisions

### 1. 三类 @ 语义

| 类型 | 示例 | 存储 | 触发 |
|------|------|------|------|
| 用户 @ Bot | UI 选择 / `mention_bot_ids` | user 消息字段 | **100% 串行回复** |
| Bot @ Bot | 正文 `@高冷理工男` | 解析 → `parsed_mention_bot_ids` | `auto_reply_pct` 掷骰后串行接话 |
| 任意 @ 用户 | `@用户` 或配置昵称 | `mention_user: true` 或装饰标记 | **仅 UI/上下文，无 API** |

### 2. @ 谁：模型在提示词里选（✅ 用户 2026-06-06）

群环境 system 追加指引（示例）：

```text
你可以在回复中使用 @成员名 点名其他机器人，或使用 @用户 称呼人类用户。
若需要让某位成员接话，请 @该成员的名字。
不要 @自己。一次可 @ 一人或多人（将按顺序回应）。
```

后处理从 assistant `content` 用成员名表解析 `@Bot名` → `bot_id` 列表（顺序保留）。

### 3. 混合 @ 处理（✅ 用户 2026-06-06）

对每个 **即将展示的** Bot 回复：

1. 取模型原始 `content`
2. `parse_mentions(content)` → `bot_ids[]`, `has_user_mention`
3. 若 `bot_ids` 为空 **且** 群 `auto_interaction_enabled` **且** 掷中该 Bot 的 `auto_mention_pct`：
   - 调用轻量规则或二次 prompt 补 @（**优先**：在文末追加一句带 @ 的短句，@ 对象仍由 **模型在补全 prompt 里选**；无模型则 fallback 随机另一成员）
4. 合并解析结果，写回消息元数据 `speaker_bot_id` + 展示用正文

> 混合 = **模型正文优先**；概率层只在「模型没 @」时补一刀，且补 @ 仍走模型选目标（小 prompt）而非纯随机。

### 4. 串行回复（✅ 用户 2026-06-06）

- 用户 @ [A, B]：先 A 后 B（已有）
- Bot A 正文 @ B：B 入接话队列，**一条一条** `send_group_bot_reply`
- 同一轮接话链内：**FIFO 队列**，不并行

### 5. auto_reply_pct 作用域

| 触发来源 | auto_reply_pct |
|----------|----------------|
| 用户消息 `mention_bot_ids` | **不掷骰，100% 回复** |
| Bot 消息解析出的 `@Bot` | 掷骰；未命中则不入队 |
| `auto_interaction_enabled == false` | Bot 互 @ 不触发接话（仅展示正文里的 @） |

### 6. 接话链与防循环

```text
用户消息
  → 用户 @ 队列（必回，串行）
  → 每条 Bot 回复完成 → parse @ → auto_reply 过滤 → 入 bot_chain_queue
  → 弹出下一 Bot → 回复 → 重复
  → 直到队列为空 或 chain_round >= max_chain_rounds（默认 3）
```

- `max_chain_rounds`：只计 **Bot 引发的接话**，不计用户直接 @ 的首轮
- 可选：同一 Bot 在同一链内最多发言 1 次（防刷屏）

### 7. 群配置数据模型

`groups/{id}/meta.json` 扩展：

```json
{
  "id": "...",
  "name": "小分队",
  "member_bot_ids": ["a", "b", "c"],
  "auto_interaction_enabled": false,
  "max_chain_rounds": 3,
  "member_settings": {
    "bot_a": { "auto_mention_pct": 40, "auto_reply_pct": 80 },
    "bot_b": { "auto_mention_pct": 20, "auto_reply_pct": 50 }
  }
}
```

- `member_settings` 键为 `bot_id`；缺省成员用默认 20/40
- 索引 `groups.json` 可冗余 `auto_interaction_enabled` 供列表展示

### 8. @用户 纯装饰（✅ 用户 2026-06-06）

- 用户输入可选 @用户 chip（与 @Bot 并列，无 `bot_id`）
- 消息字段：`mention_user: true` 或 `mention_targets: [{type:"user"}]`
- Bot 正文出现 `@用户`：前端高亮，写入历史，**不调用** `send_group_bot_reply`
- 群 system 中固定一行：`人类用户显示为 @用户`

### 9. 前端展示

- 用户/Bot 消息中 `@用户`：浅色标签样式
- Bot 消息中 `@Bot名`：对应成员色
- 群设置：编辑群 → 总开关 + 成员表双滑块（0–100%）

## 接话状态机（后端）

```text
states: idle | user_replies | bot_chain
events:
  USER_SEND(mention_ids) → user_replies (queue = mention_ids)
  USER_REPLY_DONE → parse @ → maybe bot_chain
  BOT_REPLY_DONE → parse @ → enqueue → bot_chain or idle
  CHAIN_LIMIT → idle
```

`chain_depth` 在 session 内存或单次 send 事务内计数，不持久化。

## Risks

- 模型乱 @ / 幻觉名 → 解析失败则忽略，记录 debug 日志
- Token 与等待时间随链长上升 → 默认关 auto_interaction，低默认概率
- 补 @ 小 prompt 增加延迟 → 仅在没有 @ 且掷中 mention 时触发

## 已关闭决策

| 问题 | 答案 |
|------|------|
| @ 谁 | 模型在提示词里选 |
| 多 @ 调度 | 串行 |
| @ 生成 | 混合（模型 + 概率补 @） |
| @用户 | 纯装饰 |
