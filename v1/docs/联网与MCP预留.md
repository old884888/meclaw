# 联网与 MCP（Phase B 预留）

## 当前实现（Phase A）

- 勾选技能 **联网搜索** 或 Bot `web_search: true`
- 后端在 Chat Completions 请求中加入 `tools: [{ type: "function", name: "search_web", ... }]`
- **多轮工具循环**：模型返回 `tool_calls` 时执行检索并追加 `role: tool`，可继续带 tools 请求直到不再调用或达到 `web_search_max_rounds`（默认 3）
- 每轮最多 `web_search_max_queries_per_round` 条 `search_web`（默认 3）
- 默认 provider：**Bing 本地**（HTML/RSS 抓取，无需 Key）；可改 `duckduckgo` 或 `serpapi` + `web_search_api_key`
- 前端：消息气泡顶部 **联网时间线**（每条检索可点开详情）、**共 N 条引用** 抽屉；历史消息可恢复

## 为何不用 `type: web_search`

部分 OpenAI 兼容端点仅接受 `function` 工具，发送 `web_search` 会返回 400。

## MCP Phase B（未实现）

预留扩展点：

```json
{
  "mcp_servers": [
    {
      "id": "search",
      "command": "...",
      "env": { "SERPAPI_KEY": "..." }
    }
  ]
}
```

由独立 MCP 宿主进程暴露工具，MeClaw 作为客户端聚合；适合企业自建检索，不作为默认路径。
