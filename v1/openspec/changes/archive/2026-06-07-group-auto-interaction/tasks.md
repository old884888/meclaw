# Tasks — group-auto-interaction

> 依赖 `group-chat-mode` Phase 1 已落地。决策已关闭（2026-06-06）。

## 0. 决策关闭

- [x] 0.1 @ 谁：模型在提示词里选
- [x] 0.2 多 @：串行回复
- [x] 0.3 @ 生成：混合处理
- [x] 0.4 @用户：纯装饰
- [x] 0.5 确认 `max_chain_rounds` 默认值（3）

## 1. 数据模型

- [x] 1.1 `meta.json` 增加 `auto_interaction_enabled`、`max_chain_rounds`、`member_settings`
- [x] 1.2 `update_group` / `create_group` 读写新字段
- [x] 1.3 消息扩展：`mention_user`、`parsed_mention_bot_ids`（assistant）

## 2. 解析与混合 @

- [x] 2.1 `parse_bot_mentions(text, member_bots)` 按名匹配
- [x] 2.2 群 prompt 追加 @ 使用指引（模型选目标）
- [x] 2.3 `auto_mention_pct` 掷骰 + 模型补 @ 小 prompt（混合）
- [x] 2.4 `@用户` 识别与装饰标记

## 3. 接话状态机

- [x] 3.1 用户 @ 队列（100% 串行，已有逻辑复用）
- [x] 3.2 Assistant 回复后 parse → `auto_reply_pct` → 入队
- [x] 3.3 `max_chain_rounds` 截断
- [x] 3.4 同链同 Bot 最多 1 次（spoken_bot_ids）

## 4. 前端

- [x] 4.1 群编辑：总开关 + 成员双滑块
- [x] 4.2 输入区 @用户 chip（装饰）
- [x] 4.3 消息渲染：`@用户` / `@Bot` 高亮
- [ ] 4.4 接话中 loading 提示（可选）

## 5. 文档与验收

- [x] 5.1 更新 `docs/记忆系统使用帮助.md` 群自动接话说明
- [ ] 5.2 验收：关 auto 时 Bot 互 @ 不接话；开 + 高概率接话；用户 @ 仍必回；@用户 无 API
