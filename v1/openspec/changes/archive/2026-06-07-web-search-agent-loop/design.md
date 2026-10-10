## Context

**当前状态**

- `backend/api.py` → `_call_api`：联网时仅 **1 次** 非流式 `tools=True` 请求 → 执行 `tool_calls` → **1 次** 流式最终回复
- `backend/web_search.py` → `search_web()` 返回 **纯文本**，前端无法解析为引用卡片
- `web/js/chat.js` → `onWebSearchStatus` 单条临时状态，正文 token 开始后 `end` 清除；无法展示多条检索时间线
- 已有 Bing local + RSS 回退、provider 标签、skipped/error 阶段（近期改动）

**参考 UX**（Kelivo / DeepSeek 类客户端）

- 气泡顶部竖线时间线：每条「🌐 联网检索：{query}」可展开
- 多轮：搜 → reasoning → 再搜 → … → 最终正文
- 「共 N 条引用」底部抽屉；点开单次检索可见参数 + 结果（JSON 或卡片）

**约束**

- 保持 `type: function` 的 `search_web`，不用 `type: web_search`
- pywebview `evaluate_js` 推送，无 WebSocket
- 人设沉浸：默认 UI 展示人类可读信息，原始 JSON 折叠
- 成本：每多一轮 = 1 次完整 API prefill + N 次 Bing 请求

## Goals / Non-Goals

**Goals:**

- 实现文档承诺的 **多轮工具循环**（默认最多 3 轮），轮间推送 reasoning
- 每次 `search_web` 产生结构化 `WebSearchStep`，前端追加时间线行（不覆盖）
- 聚合所有 step 的 `items` 为 **去重 citations**，提供引用抽屉
- 流式结束与会话历史中可恢复时间线 + 引用
- 可配置 `web_search_max_rounds`、`web_search_max_queries_per_round`

**Non-Goals:**

- MCP 宿主、多 provider Router（Kelivo 级）、正文 `[1]` 脚注联动（二期）
- 轮询间隔/定时器（非 polling 模型）
- 群聊独立联网 UI（首期与私聊共用组件，群聊消息结构后续对齐）
- 修改 prompt-cache 分层策略（tool 轮次自然增加 dynamic 尾部，不专项优化）

## Decisions

### 1. Agent 循环放在 `_call_api`，非流式轮次 + 末轮流式

```
while round < max_rounds:
    resp = _chat_completion_once(messages, tools=True)
    if no tool_calls: break
    emit reasoning from resp (if any)
    for each search_web in tool_calls (cap per round):
        execute → append tool message
        emit onWebSearchStep({ stepId, query, items, status })
    append assistant + tool messages
stream final (_stream_chat_completion, tools=False)
```

**理由**：与 OpenAI/DeepSeek tool 协议一致；轮间 reasoning 需在非流式 message 里读取。  
**备选**：全程流式 + 中途 tool — 各厂商 delta 格式不一致，复杂度高，否决。

### 2. `search_web` 双输出：`SearchResult` dataclass

```python
@dataclass
class SearchResult:
    query: str
    provider: str
    items: list[dict]  # {index, title, url, snippet}
    text_for_model: str
    error: str | None
```

- `text_for_model`：保持现有 header + 列表文本，写入 `role: tool` content
- `items`：仅推前端与 citations 聚合，不进 API（避免 token 膨胀）

**理由**：模型侧零破坏；UI 获得结构化数据。  
**备选**：tool content 用 JSON — 模型阅读体验差，否决。

### 3. 前端事件：`onWebSearchStep` 追加，`onWebSearchStatus` 降级为轮次级

| 事件 | 用途 |
|------|------|
| `onWebSearchStatus` | 轮次级：analyzing / round_start / skipped / error |
| `onWebSearchStep` | 步级：每条检索 append/update（searching → done/failed） |
| `onStreamDone` | 增加 `webSearchSteps`, `citations` 持久化 |

时间线 DOM：`.web-search-timeline` 置于 `.message-bubble` 顶部，竖线 + 多行 `.web-search-step`。

**理由**：步级与轮级分离，避免单条 status 覆盖。  
**备选**：仅扩展 `onWebSearchStatus` — 无法表达列表，否决。

### 4. 引用抽屉：URL 去重，稳定编号

- 遍历所有 step 的 `items`，按 `url` 去重（保留首次出现顺序）
- 编号 1..N 供抽屉展示；与正文 `[n]` 联动留二期

### 5. 详情面板：卡片默认 + 原始数据折叠

点击时间线 `>` 打开 modal/sheet：

- **参数**：`{ "query": "..." }`
- **结果**：表格/卡片（title、snippet、外链）
- **原始数据**（`<details>`）：`params` + `items` JSON + `text_for_model` 前 2KB

**理由**：兼顾普通用户与调试；符合「不默认怼 JSON」的沉浸要求。

### 6. 配置默认值

| Key | 默认 | 范围 |
|-----|------|------|
| `web_search_max_rounds` | 3 | 1–5 |
| `web_search_max_queries_per_round` | 3 | 1–8 |

超出时：截断当轮多余 `tool_calls` 并 log 警告，不 silent fail。

### 7. 历史消息持久化

`onStreamDone` payload：

```json
{
  "reasoning": "...",
  "content": "...",
  "webSearchSteps": [{ "id", "query", "provider", "status", "resultCount", "items" }],
  "citations": [{ "index", "title", "url", "snippet" }]
}
```

`saveSession` / 消息 JSON 存入现有会话结构；重载时用 `renderWebSearchTimeline(steps)` 重建 DOM。

**备选**：仅存后端 — pywebview 架构下前端持会话，沿用现有模式。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 多轮 API 成本与延迟显著上升 | 默认 3 轮 + 每轮 query 上限；设置页说明 |
| 单条消息 DOM 过大（12+ 检索） | items 每步最多 8 条；详情按需展开 |
| reasoning 轮次与检索交错展示乱序 | 时间线按 step 完成顺序 append；reasoning 仍在 thinking-block |
| 群聊/重答复用 streaming-msg id | 时间线绑定 `streaming-msg`；`onStreamDone` 后 id 移除前写入 data 属性 |
| 旧会话无 `webSearchSteps` | 前端缺字段时静默跳过，不报错 |

## Migration Plan

1. 后端：结构化 `search_web` + agent loop（行为变更，配置默认与现网接近）
2. 前端：新时间线组件；保留旧 `onWebSearchStatus` 兼容一轮场景
3. 配置：`config.example.json` 增两项；旧 config 缺省用默认 3/3
4. 文档与 skill 说明更新
5. 回滚：关闭多轮（`max_rounds=1`）即退化为现行为；UI 可 feature-flag

## Open Questions

- 群聊多 Bot 连发时，时间线是否按 Bot 分色？（首期：统一时间线，群聊 follow-up）
- `max_rounds=1` 时是否仍展示时间线？（建议：是，改善可观测性）
- 检索失败是否自动重试 provider？（首期：保持 Bing→DDG 现有回退，不加重试轮）
