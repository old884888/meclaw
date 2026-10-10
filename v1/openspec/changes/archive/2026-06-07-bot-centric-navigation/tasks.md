# Tasks — bot-centric-navigation

> 决策已关闭（2026-06-05：Q1–Q5 均为 A）。可进入实现。

## 0. 决策关闭

- [x] 0.1 Q1-A：二级列表顶栏强制同步 `selectedBotId` 只读
- [x] 0.2 Q2-A：历史遗留在 Bot 列表最底部
- [x] 0.3 Q3-A：卡片模式标签 = DeepSeek 思考/快速
- [x] 0.4 Q4-A：P0+P1 一次交付
- [x] 0.5 Q5-A：群聊 Tab 灰色占位「即将推出」

## 1. 后端 API

- [x] 1.1 `get_sessions(bot_id?)` 支持过滤；`bot_id=''` 表示仅遗留
- [x] 1.2 `new_session(bot_id?)` 显式绑定 Bot
- [x] 1.3 `switch_bot` 在有绑定 session 时拒绝切换（可选双保险）

## 2. 前端 — 导航状态

- [x] 2.1 引入 `sidebarView` / `selectedBotId` 状态
- [x] 2.2 `renderBotList()` 第一层
- [x] 2.3 `renderBotSessionList(botId)` 第二层 + 返回
- [x] 2.4 `renderLegacySessionList()` 历史遗留

## 3. 前端 — 交互

- [x] 3.1 第二层「+ 新建对话」调用 `new_session(selectedBotId)`
- [x] 3.2 会话内禁用顶栏 `switchBot`；`switchSession` 后同步只读展示
- [x] 3.3 空状态 CTA「和它开始第一个对话」
- [x] 3.4 搜索按 Bot 分组（`renderSearchResults` 改造）
- [x] 3.5 多选仅第二层；调整 `enterMultiSelectMode` 入口

## 4. 前端 — 样式

- [x] 4.1 Bot 行、会话卡片（头像+名+模式标签）
- [x] 4.2 历史遗留栏样式
- [x] 4.3 群聊 Tab 灰色禁用 + tooltip「即将推出」

## 5. 验收

- [ ] 5.1 两 Bot 各多 session，导航与排序正确
- [ ] 5.2 会话内无法换 Bot；换 session 自动切只读 Bot 展示
- [ ] 5.3 遗留 session 不进 Bot 列表；可从遗留栏打开
- [ ] 5.4 记忆检索仍按 session 所属 Bot 的 soul_folder
