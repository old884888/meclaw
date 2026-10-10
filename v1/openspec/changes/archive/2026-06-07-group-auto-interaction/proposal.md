## Why

群聊 Phase 1 仅支持「用户 @ Bot → Bot 回复」。用户希望群更像真实群聊：**Bot 会主动 @、Bot 之间能接话**，并用 **群级开关 + 每 Bot 双概率** 控制热闹程度与 API 成本。

## What Changes

- Bot 回复正文中可使用 `@成员名` / `@用户`（提示词引导 **由模型选择** @ 谁）
- **混合 @ 处理**：模型正文解析 `@Bot` 为主；若掷中 `auto_mention_pct` 且正文无 @，后处理补一条 @
- Bot 消息中解析到 `@Bot` → 触发 **串行接话链**（与现有多 @ 用户消息一致）
- `@用户`：**纯装饰**（UI 高亮 + 上下文展示），不触发 API
- 群 `meta.json` 扩展：`auto_interaction_enabled` + 每成员 `auto_mention_pct` / `auto_reply_pct`（0–100）
- 群设置 UI：总开关 + 成员双滑块
- 接话链 **轮次上限**（默认 3，可配置）防 A↔B 死循环

## Capabilities

### New Capabilities

- `group-auto-interaction`: Bot 互 @ 接话、混合 mention、群级概率设置、@用户装饰

### Modified Capabilities

- `group-chat`: 消息路由从「仅 user 触发」扩展为「user + assistant 解析 @ 触发」

## 用户已确认决策（2026-06-06）

| 项 | 决策 |
|----|------|
| @ 谁 | **模型在提示词里选**（非随机点名、非固定模板） |
| 多 Bot 被 @ | **依旧串行回复** |
| @ 生成方式 | **混合**：模型为主 + 概率未命中时后处理补 @ |
| @用户 | **纯装饰**，无 API 作用 |
| 用户 @ Bot | 沿用 Phase 1：**100% 回复**（不受 auto_reply_pct 影响） |

## 默认待定（实现前可改）

| 项 | 建议默认 |
|----|----------|
| 单次用户消息触发的 Bot 接话链上限 | 3 轮（不含用户直接 @ 的首次回复） |
| `auto_interaction_enabled` 默认 | `false` |
| 默认 `auto_mention_pct` / `auto_reply_pct` | 20 / 40 |

## Impact

- **后端**：`group_mention_parser`、接话状态机、`meta.member_settings`、prompt 扩展
- **前端**：群编辑设置、消息 `@用户` / `@Bot` 高亮、接话进度（可选）
- **成本**：每接话一轮 = 一次 API；受概率与轮次上限约束
