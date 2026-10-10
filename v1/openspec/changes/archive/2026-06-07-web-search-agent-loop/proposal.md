## Why

MeClaw 已支持 `search_web` 与 Bing 本地检索，但联网体验与主流客户端（Kelivo / DeepSeek 类）差距明显：当前仅 **单轮** 工具调用（搜完即流式回复），无法「搜 → 思考 → 再搜」；前端只有 **临时状态条**，多条检索会互相覆盖，用户无法确认是否在联网、搜了什么、找到几条来源。文档 `docs/联网与MCP预留.md` 已写明「最多 3 轮」但代码未实现。需要在不引入 MCP 的前提下补齐 **Agent 工具循环** 与 **持久化联网时间线 + 引用界面**，提升可观测性与复杂问题的检索质量。

## What Changes

- **多轮工具循环**：`_call_api` 在联网开启时循环调用带 `tools` 的非流式请求，执行 `search_web` 后把 tool 结果追加回消息，直到模型不再返回 `tool_calls` 或达到 `web_search_max_rounds`（默认 3）；轮间 reasoning 照常推送到思考区
- **结构化检索结果**：`search_web` 内部返回 `{ query, provider, items[], text_for_model, error }`；给模型仍拼文本，给前端/UI 用结构化 `items`（title、url、snippet、index）
- **持久联网时间线**：替换/增强现有 ephemeral `onWebSearchStatus` 条，在 AI 气泡顶部展示「🌐 联网检索：{query}」列表，每条显示状态与结果条数，流式结束后保留在历史消息中
- **引用抽屉**：正文下方「共 N 条引用」按钮，打开侧滑/底部面板，展示去重后的来源列表（编号、标题、摘要、URL）
- **检索详情**：点击时间线某一项，展示参数（query JSON）与结果卡片；底部提供「查看原始数据」折叠区（tool 原始 JSON / 文本），默认隐藏
- **配置项**：`web_search_max_rounds`（默认 3）、`web_search_max_queries_per_round`（默认 3，防单轮爆炸）；设置页可配置
- **会话持久化**：`onStreamDone` 携带 `webSearchSteps` 与 `citations`，历史消息重渲染时可恢复时间线与引用
- **保留**：现有 Bing local / DuckDuckGo / SerpAPI provider、`SEARCH_WEB_TOOL` function 形态、不引入 `type: web_search` API 工具

## Capabilities

### New Capabilities

- `web-search-agent-loop`: 多轮 `search_web` 工具循环、轮次/每轮 query 上限、轮间 reasoning 与最终流式回复衔接
- `web-search-timeline`: 结构化检索结果协议、前端联网时间线、引用抽屉、单步详情与历史消息持久化

### Modified Capabilities

<!-- 无 main specs 中的既有联网 spec；归档变更中的 web-search 行为由本变更在新 spec 中完整定义 -->

## Impact

- **后端**：`backend/api.py`（`_call_api` 工具循环、`_execute_search_tool_calls`、新 `onWebSearchStep` 推送）；`backend/web_search.py`（结构化 `SearchResult`、解析 Bing/RSS 为 items）
- **前端**：`web/js/chat.js`（时间线组件、引用抽屉、详情面板）；`web/style.css`；`web/index.html` / `web/js/config.js`（新配置项）
- **配置**：`config.example.json`、`backend/api.py` 默认配置
- **文档**：`docs/联网与MCP预留.md`、`skills/web-search/instructions.md`
- **无新运行时依赖**；API 调用次数与延迟随轮次增加，需上限保护
