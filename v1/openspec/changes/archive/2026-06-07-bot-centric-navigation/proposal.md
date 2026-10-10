## Why

MeClaw 侧边栏当前为**全局扁平会话列表**，顶栏可随时 `switch_bot` 并清空对话，导致「一个会话频繁换人设」、卡片无法识别所属 Bot，与用户对「微信式好友 + 多话题对话栏」的心智模型不符。后端已有 `session.bot_id` 与 Bot 级 `souls/{id}/memory/`，主要缺口在**前端导航范式**与**会话内 Bot 锁定**。

## What Changes

### Phase 1 — 私聊导航改版（本变更范围）

- 侧边栏「对话」Tab 第一层改为 **Bot 列表**（通讯录感）
- 点击 Bot 进入第二层：**仅该 Bot 下的会话列表**，顶栏「← 返回」回到 Bot 列表
- 「+ 新建对话」**仅在第二层显示**，新建会话 `bot_id` 固定为当前 Bot
- 进入已有会话后，顶栏 Bot 名**只读**（禁止 `switch_bot` 换人设）
- 在 Bot 列表层（未进入会话），顶栏 Bot 选择器**仍可用**，表示「接下来新建对话默认用谁」（与第二层语义分离，见 design 决策 3）
- 会话卡片显示：**头像 + Bot 名 + 模式标签**（详略见待决问题）
- 各 Bot 内会话按 `updated_at` **倒序**排列
- 搜索：结果**按 Bot 分组**展示
- 多选删除：保留，**仅在某 Bot 的会话列表层**可用
- 某 Bot 无会话：空状态 +「和它开始第一个对话」
- `bot_id` 为空的旧会话：归入 **「历史遗留」** 单独一栏（不自动补写 bot_id）
- **本阶段不写群聊功能**；侧边栏显示灰色「群聊」Tab 占位「即将推出」（Q5-A）
- **P0+P1 同一迭代交付**（Q4-A）：卡片标志、锁 Bot、两层导航一并实现

### 不在本变更范围

- 群聊实体、@ 回复、群记忆（见 `group-chat-mode` 变更）
- 记忆整理代理 Bot/API 选择器（见 design 关联能力，可后续独立小变更）

## Capabilities

### New Capabilities

- `bot-centric-sidebar`: 两层 Bot → Session 导航、会话锁定 Bot、卡片信息增强、分组搜索、历史遗留栏

### Modified Capabilities

- （无既有 openspec 规格破坏性修改；`bot-memory` 行为不变，仍 per-bot 跨 session 共享）

## Impact

- **前端（主战场）**：`web/js/sidebar.js`、`web/index.html`、`web/style.css`、`web/js/bot.js`、`web/app.js`
- **后端（小补）**：`get_sessions(bot_id?)`、`new_session(bot_id?)`；可选 `switch_bot` 在校验当前 session 时拒绝
- **数据**：`history/sessions.json` **无需迁移**；空 `bot_id` 会话原样保留
- **记忆 / 压缩 / 发消息主链路**：不改动

## 用户已确认决策（2026-06-05）

| # | 决策 |
|---|------|
| 导航 | 第一层 Bot 列表 → 第二层该 Bot 会话列表 |
| 新建 | 仅第二层；固定属于当前 Bot |
| 锁 Bot | 会话内顶栏 Bot 只读 |
| 顶栏（列表层） | 仍显示 Bot 选择器，表示默认新建对象 |
| 卡片 | 头像 + Bot 名 + 模式标签 |
| 排序 | 各 Bot 内 `updated_at` 倒序 |
| 搜索 | 按 Bot 分组 |
| 多选 | 保留，仅 Bot 会话列表层 |
| 空 Bot | 空状态 + 开始第一个对话 |
| 遗留 | 空 `bot_id` 单独「历史遗留」栏 |
| 群聊 | 本阶段不做；Tab 灰色占位「即将推出」 |
| Q1–Q5 | A/A/A/A/A（见 design.md） |
