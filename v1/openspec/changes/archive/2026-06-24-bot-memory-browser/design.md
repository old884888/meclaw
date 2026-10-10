## Context

已有能力：

- **存储布局**（`paths.py`）：`souls/{bot_id}/memory/l0|l1|l2|l3/`，L2 会话摘要也在 `history/summaries/`。
- **后端 API**（`main.py`）：`GET /memory/l1`、`GET /memory/l3`、`DELETE /memory/l1/{atom_id}`。
- **超级大脑状态面板**：展示 L0/L1/L2 计数、索引状态、最近召回，但不可 drill-down。
- **检索**（`indexer.search_memory`）：编排器内部用，无对外 HTTP API。

用户诉求：看清「这个 Bot 记住了什么」，并能在 L1 层面纠正错误记忆。

## Goals / Non-Goals

### Goals

- 单一入口：从状态面板「记忆层级」进入记忆库。
- 四层 Tab：L0 证据 / L1 原子 / L2 摘要 / L3 画像。
- L1 支持软删除；删除后刷新 brain status 计数。
- L2 显示会话标题 + 摘要片段，可跳转该会话。
- 可选搜索框，调用 `search_memory` 跨层检索（结果以 L1 为主）。
- 分页或 limit 参数，避免一次加载上千条 L0。

### Non-Goals

- L3 编辑、L2 手动改写。
- L0 删除。
- 独立顶栏按钮（避免与说明书/状态/设置拥挤）。

---

## UX Placement

### 入口

在 **超级大脑状态面板 → 记忆层级** 区块：

- L0/L1/L2 数字行可点击，默认打开对应 Tab。
- 增加「查看记忆库」文字链，默认打开 L1 Tab。

可选第二入口（非第一版）：Bot 编辑器「记忆」Tab。

### 记忆库布局

```
┌─ 记忆库 · {Bot 名} ─────────────────── [✕] ┐
│ [L0 证据] [L1 原子] [L2 摘要] [L3 画像]      │
│ 🔍 搜索记忆…（L1 Tab 或全局 search API）     │
├──────────────────────────────────────────┤
│ L1 列表示例：                              │
│  [preference] 用户喜欢简洁回答              │
│  会话 s_xxx · 2026-06-20        [删除]   │
│  [todo] 实现记忆查看入口                    │
│  会话 s_yyy · 2026-06-21        [删除]   │
└──────────────────────────────────────────┘
```

### Tab 内容

| Tab | 数据源 | 列表项 | 操作 |
|-----|--------|--------|------|
| L0 | `GET /memory/l0?session_id=&limit=&offset=` | 回合证据、user/assistant 片段 | 只读；按 session 分组 |
| L1 | `GET /memory/l1`（已有） | type + content + session + 时间 | 删除 |
| L2 | `GET /memory/l2?limit=` | 会话标题 + 摘要前 N 字 | 点击跳转会话 |
| L3 | `GET /memory/l3`（已有） | 完整 profile Markdown | 只读 |

### Type 徽章颜色（L1）

| type | 颜色 | 含义 |
|------|------|------|
| fact | 蓝 | 事实 |
| preference | 绿 | 偏好 |
| constraint | 橙 | 约束 |
| todo | 紫 | 待办 |

### 空状态

- 新 Bot：`发几轮对话后，记忆会自动出现在这里。`
- L3 未配置：`尚未生成用户画像。`

---

## API Design

### GET `/api/bots/{bot_id}/memory/l0`

Query: `session_id?`, `limit` (default 20), `offset` (default 0)

Response:

```json
{
  "ok": true,
  "items": [
    {
      "session_id": "s_xxx",
      "created_at": "...",
      "message_count": 2,
      "preview": "user: … / assistant: …"
    }
  ],
  "total": 42
}
```

Implementation: glob `l0_dir/*.json`，可选按 `session_id` 过滤；preview 从 messages 截取。

### GET `/api/bots/{bot_id}/memory/l2`

Query: `limit` (default 20)

Response:

```json
{
  "ok": true,
  "items": [
    {
      "session_id": "s_xxx",
      "title": "新对话",
      "summary": "…",
      "updated_at": "..."
    }
  ]
}
```

Implementation: `list_session_summaries(history_dir, bot_id, sessions_index, limit)`.

### GET `/api/bots/{bot_id}/memory/search`

Query: `q` (required), `limit` (default 10)

Response:

```json
{
  "ok": true,
  "items": [
    { "type": "fact", "snippet": "…", "session_id": "…", "score": 0.8 }
  ]
}
```

Implementation: `search_memory(paths, q, limit)`.

### Existing（不变）

- `GET /memory/l1` — 可后续加 `limit`/`offset`
- `GET /memory/l3`
- `DELETE /memory/l1/{atom_id}`

---

## Frontend State

```javascript
state.memoryBrowser = {
  open: false,
  botId: null,
  tab: "l1",       // l0 | l1 | l2 | l3
  items: [],
  loading: false,
  searchQuery: "",
  sessionFilter: null,  // optional from status panel context
};
```

Flow:

1. User clicks L1 count in status panel → `openMemoryBrowser({ botId, tab: "l1" })`.
2. Load tab data via API.
3. Delete L1 → confirm → DELETE → reload tab + `loadBrainStatus({ silent: true })`.

---

## Risks / Mitigations

| 风险 | 缓解 |
|------|------|
| L0 文件过多导致慢 | limit/offset；默认 20 |
| L1 列表无分页 | 第一版 limit 100；后续分页 |
| 删除 L1 后索引 stale | 软删已写 audit；可选 rebuild index 按钮（非第一版） |
| 与状态面板 modal 叠层 | 记忆库用独立 modal 或嵌套 sheet；关闭记忆库回到状态面板 |

---

## Testing

- API smoke: L0/L2/search 404 on bad bot_id；空 Bot 返回 `items: []`。
- 有 L1 的 Bot：list 非空；delete 后 count 减 1。
- 手动：状态面板 → 点 L1 → 看到列表 → 删一条 → 状态计数更新。
