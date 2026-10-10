## Context

- **现状**：`sidebar.js` → `renderSessionList()` 扁平渲染；`switch_session` 已按 `bot_id` 切 `active_bot_id`；`new_session()` 用 `get_active_bot()` 写 `bot_id`；`switch_bot()` 会清空 `currentSessionId` 与对话区。
- **目标**：微信私聊式「好友（Bot）→ 多个话题（Session）」；记忆仍在 Bot 级 `souls/{id}/memory/`，跨 session 检索不变。
- **约束**：pywebview + 现有 `history/` 文件结构；不强制迁移旧数据。

## Goals / Non-Goals

**Goals:**

- 两层侧边栏导航 + 会话内 Bot 锁定
- 会话卡片可识别 Bot 与模式
- 搜索、多选、空状态、历史遗留栏
- 后端 API 小扩展（按 bot 过滤/创建）

**Non-Goals:**

- 群聊（独立变更 `group-chat-mode`）
- 重写 `history.py` 存储格式
- 修改 `bot-memory` 检索与压缩双管线逻辑

## Decisions

### 1. 前端导航状态机

```text
sidebarView: 'bots' | 'bot-sessions' | 'legacy-sessions'
selectedBotId: string | null      // 进入第二层时设置
currentSessionId: string | null   // 进入聊天区时设置
```

- `bots`：渲染 Bot 列表 + 底部「历史遗留」入口（若有空 bot_id 会话）
- `bot-sessions`：渲染 `selectedBotId` 下会话；工具栏「+ 新建对话」「多选」「← 返回」
- 切换 `switchSession` 后 `sidebarView` 保持 `bot-sessions`（或 `legacy-sessions`）

### 2. 会话内 Bot 只读

- 当 `currentSessionId != null`：隐藏或禁用 `#bot-selector` 下拉；仅展示头像+名+模式徽章
- 后端 `switch_bot`：若 `current_session` 存在且 `session.bot_id` 非空且与请求 `bot_id` 不同 → 返回 `{ok: false}`（双保险）

### 3. 顶栏 Bot 选择器语义（✅ Q1-A）

| 场景 | 顶栏 Bot 选择器 | 新建对话归属 |
|------|----------------|--------------|
| `sidebarView === 'bots'` | 可切换，表示全局 `active_bot_id` 默认 | 不适用（此层无新建按钮） |
| `sidebarView === 'bot-sessions'` | **强制同步为 `selectedBotId`，只读** | `new_session(selectedBotId)` |
| 已进入某 session | 只读，显示 session 的 `bot_id` | 不适用 |

进入 Bot 二级列表时立即 `syncHeaderBot(selectedBotId)`，避免顶栏与侧边栏双源冲突。

### 4. 会话卡片信息（✅ Q3-A）

每条 session 卡片展示：

- Bot 头像（`bots[].avatar`）
- Bot 名称
- **模式标签**：DeepSeek **思考 / 快速**（取自 Bot 的 `thinking_enabled` 等；非 DeepSeek Bot 不显示或显示「—」）
- 标题、时间、`message_count`（保留）

编程/对话模式（`session.mode`）不在卡片标签展示，避免与 DeepSeek 回复模式混淆。

数据：`get_sessions` 返回 `bot_id`；前端 join `cachedConfig.bots`。

### 5. 排序

- Bot 列表：按该 Bot **最近会话** `updated_at` 倒序（有会话的 Bot 排前）；无会话 Bot 按名称或创建顺序
- Bot 内会话：`updated_at` 倒序
- 历史遗留：独立列表，`updated_at` 倒序

### 6. 搜索

- 调用现有 `search_sessions(keyword)`
- 前端将结果按 `bot_id` 分组渲染（含「历史遗留」组）
- 清空搜索时恢复当前 `sidebarView` 列表

### 7. 历史遗留（✅ Q2-A）

- 条件：`session.bot_id` 为空字符串或缺失
- UI：Bot 列表**最底部**固定一行「📦 历史遗留 (N)」，点击进入与 `bot-sessions` 同布局的列表
- **不**自动补 `bot_id`、不合并进任意 Bot

### 8. 后端 API 扩展

```python
get_sessions(bot_id: str | None = None)  # None=全部；''=仅遗留
new_session(bot_id: str | None = None)   # 显式传入；缺省 fallback active_bot
```

## UI 线框（文字）

```text
[对话 Tab]  [群聊 Tab — 灰色占位「即将推出」，✅ Q5-A]

--- sidebarView: bots ---
🔍 搜索对话...
[Bot A]  高冷理工男   最近 06/05
[Bot B]  ...
...
[📦 历史遗留 (3)]

--- sidebarView: bot-sessions ---
← 返回    [+ 新建对话] [多选]
🤖 高冷理工男 · 思考
  配音技巧        06/05 · 24条
  项目 MeClaw     06/04 · 8条
```

## 关联能力（本变更不实现，记入 backlog）

### 记忆整理代理（✅ Q7-C，本变更不实现，群聊阶段或独立小变更）

- **API Profile（必选）**：压缩/记忆提取的 LLM 调用走 `memory_organizer_profile_id`
- **Bot（可选）**：`memory_organizer_bot_id` 仅注入整理任务的 system 人设（`soul.md`），**不**替代 API 端点
- 私聊中用户定向询问时，仍检索**该 Bot 自己的** `souls/{id}/memory/`

## 实施节奏（✅ Q4-A）

P0（卡片标志 + 锁 Bot）与 P1（两层导航）**同一迭代一次交付**，不做分阶段上线。

## 已关闭决策（2026-06-05）

| 问题 | 答案 |
|------|------|
| Q1 顶栏同步 | A — 二级列表强制同步 `selectedBotId` 只读 |
| Q2 历史遗留 | A — Bot 列表最底部固定入口 |
| Q3 模式标签 | A — DeepSeek 思考/快速 |
| Q4 实施节奏 | A — P0+P1 一次做完 |
| Q5 群聊 Tab | A — 灰色占位「即将推出」 |

## Risks

- 非 DeepSeek Bot 卡片模式标签需降级展示（隐藏或「—」）
- 编程模式 session 仍出现在 Bot 会话列表，仅卡片不展示 chat/code 标签
