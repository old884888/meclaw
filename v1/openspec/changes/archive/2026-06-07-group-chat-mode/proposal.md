## Why

用户需要「多个 Bot 同群、多话题对话栏」的协作形态，类似微信群。私聊导航改版（`bot-centric-navigation`）完成后，需独立支持群实体、@ 指定回复、群级记忆，且**不污染**各 Bot 私聊记忆。

## What Changes

- 侧边栏增加独立 **「群聊」Tab**（与「对话」并列）
- 群实体：成员 Bot 列表、群名称/头像、群下多 session
- 发消息：**@ 指定 Bot 才回复**（未 @ 不自动全员回复）
- 群记忆：独立 `groups/{group-id}/memory/`；各 Bot `souls/{id}/memory/` **不变**
- 私聊中 Bot 仍只检索**自己**的私聊记忆；群聊检索群记忆（与私聊隔离）
- 记忆压缩/整理：设置中可指定**整理代理 Bot** 或 **整理用 API**（与群/私聊记忆整理相关，可跨变更实现）

## Capabilities

### New Capabilities

- `group-chat`: 群 CRUD、群 session、@ 路由、群记忆目录与检索

### Modified Capabilities

- `bot-centric-sidebar`: 增加群聊 Tab 入口（本变更实现 Tab 与群导航；依赖私聊两层导航模式）

## Impact

- **数据**：`groups/groups.json` 索引 + `groups/{id}/`（设定、sessions 或共用 history 带 `group_id`）
- **后端**：群 CRUD API、群消息路由（@ 解析）、`search_group_memory()`、session 扩展 `group_id` + `participant_bot_ids`
- **前端**：群聊 Tab、群列表 → 群 session 列表、输入框 @ 选择器
- **记忆**：新目录 `groups/{id}/memory/`；`bot-memory` 私聊路径不改

## 用户已确认决策（2026-06-05）

| 项 | 决策 |
|----|------|
| 时机 | 私聊改版完成后再做 |
| 回复 | @ 指定 Bot 才回 |
| 记忆 | 群独立 `groups/`；Bot 私聊记忆不变；私聊询问仍搜私聊记忆 |
| 整理 | 压缩/整理有开关，可指定整理 Bot 或 API |
| Tab | 单独「群聊」Tab（Phase 1 灰色占位） |
| Q6–Q8 | B / C / A（见 design.md） |
| Q0.4 @ 交互 | A — 输入框 @ 成员选择器 |

## 依赖

- `bot-centric-navigation` 合并或归档后启动实现
