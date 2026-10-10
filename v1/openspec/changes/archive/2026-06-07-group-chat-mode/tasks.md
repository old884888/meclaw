# Tasks — group-chat-mode

> **阻塞**：`bot-centric-navigation` 完成并验收后再启动。

## 0. 决策关闭

- [x] 0.1 Q6-B：未 @ 可发送，无 Bot 回复
- [x] 0.2 Q7-C：整理 API 负责调用；Bot 仅 system 人设
- [x] 0.3 Q8-A：复用 `history/` + `group_id`
- [x] 0.4 Q0.4-A：输入框 @ 弹出群成员列表选择

## 1. 数据与 API

- [x] 1.1 `groups/groups.json` + `groups/{id}/meta.json`
- [x] 1.2 `groups/{id}/memory/` 目录与 FTS（复用 `backend/memory/` 抽象）
- [x] 1.3 session 扩展 `group_id`、`member_bot_ids`；与 `bot_id` 互斥校验
- [x] 1.4 群 CRUD、群 session CRUD API

## 2. 消息路由

- [x] 2.1 @ 解析 / `mention_bot_id`
- [x] 2.2 群消息仅调用被 @ Bot 的 `build_messages_for_api`
- [x] 2.3 群记忆检索注入

## 3. 前端

- [x] 3.1 群聊 Tab + `renderGroupList` + `renderGroupSessionList`
- [x] 3.2 建群（编辑成员待后续）
- [x] 3.3 输入框 @ 触发成员下拉/浮层选择（Q0.4-A）
- [x] 3.4 群 session 卡片（群名、成员数、时间）

## 4. 记忆整理代理

- [ ] 4.1 设置 UI：`memory_organizer_*` 字段（config.example 已预留）
- [x] 4.2 `compress_context` / `extractor` 使用指定 Profile（`memory_organizer_enabled`）

## 5. 文档与验收

- [x] 5.1 更新 `docs/记忆系统使用帮助.md`（群记忆 vs 私聊记忆）
- [ ] 5.2 群 @ 回复、记忆隔离、私聊不受影响（需手动验收）
