## Context

- **编程模式**：`#file-preview` 用 `preview.js` 渲染只读 `<table>` + 简易高亮；`read_file` / `execute_file_operation` 已有 `working_dir` 越界检查。
- **联网**：曾向 API 发送 `tools: [{type: "web_search"}]`，当前端点返回 400（仅接受 `function`）。`skills/web-search` 现为提示词技能，无真实检索。
- **约束**：MeClaw 为 pywebview 桌面应用；不引入 Monaco/CodeMirror 等大依赖（首版用 `<textarea>` 或单层可编辑区）；CLAUDE 规则限制项目外破坏性操作。

## Goals / Non-Goals

**Goals:**

- 编程模式内可编辑、可保存、换行设置、脏状态、Ctrl+S / Ctrl+N
- DeepSeek 对话在启用联网技能时，走 **Function Calling + 后端执行 `search_web`**
- 设置里可配置编辑器偏好与（可选）搜索 API Key
- 更新联网技能说明，避免误导

**Non-Goals:**

- 自动补全、LSP、多标签编辑器、diff 视图
- 完整 MCP 宿主/市场（仅文档预留 Phase B）
- 终端 Agent、沙箱命令
- 非 DeepSeek provider 的联网（可显示「仅 DeepSeek」提示）

## Decisions

### 1. 编辑器实现：`<textarea>` + 行号装饰（可选简化）

**选择**：用单个 `<textarea class="code-editor">` 承载全文，换行用 CSS `white-space: pre-wrap` + `word-wrap`；行号可保留外侧窄列或首版去掉行号以降低复杂度。

**备选**：`contenteditable` + 高亮（难维护）；Monaco（体积大）。

### 2. 编辑器设置存放位置

**选择**：`config.json` 顶层字段 `editor_word_wrap: true|false`；设置弹窗新增 **「编辑器」** 卡片（与 API/外观并列）。

### 3. 保存 API

**选择**：`save_working_file(rel_path, content)` in `file_ops.py`：

```text
abs = normpath(join(working_dir, rel_path))
reject if not abs.startswith(normpath(working_dir))
write utf-8, optional backup for overwrite
```

**备选**：复用 `execute_file_operation` edit（需 AI 标记格式，不适合用户手改）。

### 4. 脏状态与 AI 冲突

**选择**：内存维护 `editorBuffer` / `lastSavedContent` 字符串比较；打开新文件或 AI 通过 `file:edit` 改同一文件时，若 buffer 脏则提示「磁盘已更新，是否重新加载」。

### 5. 联网架构：Function Calling 优先，MCP 后置

```text
用户启用 web-search 技能
    → build payload: tools = [{ type: "function", function: { name: "search_web", ... } }]
    → stream/complete until tool_calls
    → backend search_web(query) → 文本摘要
    → messages += tool result → 再次请求（上限 N 轮，如 3）
```

**为何不继续 `web_search` 类型**：实测与 DeepSeek OpenAI 兼容层不一致；官方文档以 **function** 工具为主。

**MCP（Phase B）**：独立进程/配置列表，将「搜索」注册为外部 tool provider；适合企业自建 SerpAPI。首版在 `design` 预留 `config.mcp_servers[]`，**不实现**。

### 6. 搜索后端（Phase A 默认）

**选择**：优先 **无 Key** 方案（如 `duckduckgo-search` 纯 Python 或 HTTPS 抓取封装），失败时提示配置 Key。

**备选**：仅 SerpAPI/Tavily（需用户申请 Key）— 作为 `web_search_provider: serpapi` + `web_search_api_key`。

**配置示例**：

```json
{
  "editor_word_wrap": true,
  "web_search_enabled": true,
  "web_search_provider": "duckduckgo",
  "web_search_api_key": ""
}
```

启用逻辑：`wants_web_search(bot, global_skills)` 为真时注入 `search_web` tool（与技能 ID `web-search` 或 bot.`web_search` 对齐）。

### 7. 与 composer 技能联动

勾选「联网搜索」→ 下一轮 `send_message` 带 function tools；**不**改 system prompt 为唯一手段。技能 `instructions.md` 说明「模型可调用 search_web」。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| DuckDuckGo 无官方 API，爬虫可能失效 | 可切换 provider；错误信息返回给模型与用户 |
| Tool call 循环增加延迟与 token | 限制轮次；日志面板显示「联网检索中」 |
| 大文件 textarea 卡顿 | 保留 `read_file` 截断；超大文件只读提示 |
| Ctrl+N 与浏览器冲突 | 在 pywebview 内 `preventDefault` |
| 用户未保存 + AI 改文件 | 脏检查 + 重载确认 |

## Migration Plan

1. 发布 `save_working_file` 与编辑器 UI（不破坏只读流程：默认行为改为可编辑）。
2. 部署 search 模块；默认关闭 tool loop，技能勾选后开启。
3. 更新 `skills/web-search` 与 `config.example.json`。
4. 回滚：关闭 `web_search_enabled` 或移除 tool 注入即可恢复纯聊天。

## Open Questions

- 默认搜索 provider 是否接受 `duckduckgo-search` 依赖（需写入 `requirements.txt`）？
- 新建文件（Ctrl+N）是否允许创建嵌套目录 `src/foo.py`？
- 是否在顶栏显示 🌐「联网已启用」徽章（与思考模式徽章类似）？
