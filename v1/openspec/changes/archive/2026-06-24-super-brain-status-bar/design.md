## Context

已完成或正在完成的基础能力：

- `bot-multi-brain`: 多脑子编排、Persona/Memory/Cognitive/Learner、`brain_trace`、L0-L3、Tier1-3 压缩。
- `bot-per-brain-config`: Bot 级 `brains` 覆盖、`background_model`、首页 Bot 卡片展示配置覆盖情况。
- `说明书`：已在顶栏提供说明入口，适合与状态栏形成“解释 + 运行状态”闭环。

当前问题不是缺少能力，而是缺少可视化：

- 用户不知道当前 Bot 是否真正用了记忆。
- 不知道一轮对话触发了哪些脑。
- 不知道上下文是否接近压缩。
- 不知道后台模型是否在提取 L1 或摘要。
- 供应商、Bot、记忆、压缩之间的逻辑关系不可见。

## Goals / Non-Goals

### Goals

- 顶栏常驻“超级大脑状态”胶囊，一眼可见健康状态。
- 聊天输入区展示当前会话轻状态。
- 点击状态胶囊打开详情面板，分组解释脑区、记忆、上下文、后台任务。
- 后端提供单一状态 API，前端无需到处拼读取逻辑。
- 状态栏能合并最近一次 `brain_trace`，展示本轮实际激活结果。
- 状态数据必须只读，不改变任何记忆或配置。

### Non-Goals

- 不在第一版做可编辑设置。
- 不在第一版实现后台队列管理器。
- 不在第一版做图表化长期趋势。
- 不将所有历史记忆内容展示出来，只展示统计与最近状态。

---

## UX Placement

### 1. Topbar Capsule

位置：`header.topbar > .topbar-actions`，建议放在 `说明书` 和 `设置` 之间。

示例：

```text
[说明书] [🧠 正常 · 记忆5 · 上下文33%] [设置]
```

状态颜色：

| 状态 | 颜色 | 含义 |
|------|------|------|
| `ok` | 绿色 | 多脑子/供应商/记忆状态正常 |
| `idle` | 灰色 | 未进入 Bot 或无当前会话 |
| `warn` | 黄色 | 部分功能关闭、无记忆、后台降级 |
| `error` | 红色 | Bot 不可聊天、供应商错误、状态加载失败 |

### 2. Composer Light Status

位置：现有 composer 的 `#usage-hint` 附近或替换为双行结构。

示例：

```text
约 18 条消息 · 上下文 33% · Tier0 · 记忆召回 5 · 后台空闲
```

这个区域只显示当前会话相关状态，不展示全局说明。

### 3. Detail Panel

第一版使用 modal/sheet，后续可改右侧 drawer。

分区：

1. 当前 Bot
2. 脑区
3. 记忆
4. 上下文
5. 后台任务
6. 本轮 Trace

---

## Backend API

新增：

```http
GET /api/bots/{bot_id}/brain/status?session_id=<optional>
```

返回：

```json
{
  "ok": true,
  "status": {
    "health": {
      "status": "ok",
      "label": "运行正常",
      "message": "多脑子已启用，记忆检索正常",
      "last_updated_at": "2026-06-23T17:58:00"
    },
    "bot": {
      "id": "b_xxx",
      "name": "陪聊",
      "provider_name": "OpenAI",
      "chat_ready": true,
      "config_source": "bot_override",
      "executor_model": "gpt-4o",
      "background_model": "gpt-4o-mini"
    },
    "brains": {
      "executor": { "enabled": true, "active": true, "status": "ready" },
      "persona": { "enabled": true, "active": false, "budget": 500, "tokens_used": 0 },
      "memory": { "enabled": true, "active": false, "budget": 800, "tokens_used": 0 },
      "cognitive": { "enabled": true, "active": false, "budget": 300, "tokens_used": 0 },
      "learner": { "enabled": false, "active": false, "status": "disabled" }
    },
    "memory": {
      "enabled": true,
      "retrieval_enabled": true,
      "write_enabled": true,
      "l0_count": 128,
      "l1_count": 42,
      "l2_count": 7,
      "l3_available": true,
      "index_status": "ready",
      "last_write_at": "2026-06-23T17:50:00",
      "last_recall_count": 5,
      "last_error": ""
    },
    "context": {
      "max_context": 65536,
      "estimated_tokens": 21400,
      "ratio": 0.327,
      "compact_tier": 0,
      "protection_zone_tokens": 8000,
      "summary_active": false
    },
    "background_jobs": {
      "l1_extraction": { "status": "idle", "model": "gpt-4o-mini", "last_run_at": "", "created_count": 0, "last_error": "" },
      "tier3_summary": { "status": "idle", "model": "gpt-4o-mini", "last_run_at": "", "last_error": "" },
      "learner": { "status": "disabled", "pending_signals": 0 }
    },
    "turn_trace": {
      "activated": [],
      "tokens": {},
      "compact_tier": 0,
      "context_ratio": 0.0
    }
  }
}
```

### Status Computation Rules

1. `bot` section:
   - Use `_public_bot(bot, cfg)` for readiness.
   - Use `brains_config_for_bot(cfg, bot)` for effective brain settings.
   - Use `_profile_for_bot(bot, role="executor")` and `_profile_for_bot(bot, role="background")` for model labels when possible.

2. `brains` section:
   - Executor is enabled when Bot is chat-ready.
   - Persona/Memory/Cognitive/Learner enabled from `effective_brains`.
   - Active/tokens from latest `brain_trace` when available.
   - If no trace exists, active defaults false except executor.

3. `memory` section:
   - Count files/records per Bot memory directory.
   - `l3_available` true when profile file exists and has content.
   - `index_status` can be `ready | missing | error`.
   - `last_recall_count` comes from trace when available; otherwise null/0.

4. `context` section:
   - If `session_id` exists, estimate tokens from current API-visible message history or current persisted messages.
   - If no session, ratio is 0 and tier is 0.
   - `compact_tier` prefers latest trace.

5. `background_jobs` section:
   - First version can use in-memory best-effort status:
     - default `idle`
     - L1 extraction/Tier3 summary update status around existing calls
   - If process restarts, status resets to idle.

---

## Trace Schema

Current trace already includes:

```json
{
  "activated": ["executor", "persona", "memory"],
  "tokens": { "system": 120, "persona": 300, "memory": 500 },
  "compact_tier": 0,
  "context_ratio": 0.32
}
```

This change stabilizes it for UI:

```json
{
  "activated": ["executor", "persona", "memory"],
  "tokens": {
    "system": 120,
    "persona": 300,
    "memory": 500,
    "cognitive": 0,
    "session_summary": 0
  },
  "compact_tier": 0,
  "context_ratio": 0.32,
  "memory": {
    "recall_count": 5,
    "cross_session": false,
    "l0_deep_recall": false
  },
  "models": {
    "executor": "gpt-4o",
    "background": "gpt-4o-mini"
  },
  "warnings": []
}
```

Trace remains optional; status API should work without it.

---

## Frontend State

Add state fields:

```js
state.brainStatus = null
state.lastBrainTraceBySession = {}
state.brainStatusLoading = false
```

### Loading Triggers

- After `loadBootstrap()`.
- After entering Bot workspace.
- After switching/new session.
- After WebSocket `brain_trace` event.
- After WebSocket `done`/`stopped` event, because post-turn memory may update soon.
- After Bot save / settings save.

Use lightweight reload:

```js
loadBrainStatus({ silent: true })
```

### WebSocket Integration

When event `brain_trace` arrives:

1. Save trace by `session_id` or current session id.
2. Merge trace into current `state.brainStatus.turn_trace`.
3. Rerender capsule and detail if open.

---

## UI Rendering

### Capsule Label

Priority:

1. If no selected Bot: `🧠 空闲`
2. If Bot not chat-ready: `🧠 配置错误`
3. Else:

```text
🧠 正常 · 记忆{last_recall_count} · 上下文{ratio%}
```

### Brain Dots

| Dot | Meaning |
|-----|---------|
| green filled | enabled + active |
| gray hollow | enabled + inactive |
| gray muted | disabled |
| yellow | warn/degraded |
| red | error |

### Detail Empty States

- No session: show Bot/config status only.
- Memory disabled: show “记忆脑关闭，L0/L1 写入不会执行”。
- No trace yet: show “还没有本轮 trace，发送一条消息后显示激活路径”。

---

## Backend Helpers

Suggested helpers:

- `brain_status_for_bot(bot_id: str, session_id: str | None) -> dict`
- `memory_stats_for_bot(bot_id: str) -> dict`
- `context_status_for_session(bot, session_id) -> dict`
- `runtime_job_status(bot_id: str) -> dict`

Memory stats should avoid reading all large contents:

- L0: count `*.json` in `memory/l0`
- L1: count json/md records in `memory/l1`
- L2: count summaries for bot sessions from session index + summary files
- L3: check profile file exists and non-empty
- index: check `memory/index.sqlite` exists

---

## Risks

| Risk | Mitigation |
|------|------------|
| 状态计算过重 | 只计数文件，不读大内容；缓存最近状态 |
| 状态与实际后台任务略有延迟 | UI 标注“最近状态”；done 后延迟刷新一次 |
| trace schema 变化导致 UI 崩 | 前端按缺省值容错 |
| 顶栏拥挤 | 胶囊短文案，详情放弹层 |
| memory stats 目录不存在 | helper 返回 0/missing，不报错 |

---

## Rollout Plan

1. 后端新增只读状态 API 与 memory stats helper。
2. 前端新增顶栏胶囊和详情 modal。
3. 接入 `brain_trace` 和聊天完成刷新。
4. 增加后台任务最近状态。
5. 增加测试与验收说明。
