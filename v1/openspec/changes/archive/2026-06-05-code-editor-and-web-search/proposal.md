## Why

编程模式下的文件预览目前是只读表格 + 语法高亮，无法直接改代码、保存，也没有换行等编辑器偏好；用户需要在项目内快速改文件，而不是只靠 AI 的 `file:edit` 标记。另一方面，「联网搜索」技能目前仅注入提示词，曾因 `tools: web_search` 不被当前 DeepSeek 兼容接口接受而报 400——用户需要可落地的联网方案说明与分阶段实现。

## What Changes

- 将 `#file-preview` 升级为**可编辑**工作区：文本编辑、保存、未保存/已保存状态指示
- 设置中增加 **编辑器** 分区：自动换行开关（及持久化到 `config.json`）
- 预览区工具栏：保存按钮、状态图标（未保存圆点 / 已保存勾）、保留复制与「发送给 AI」
- 快捷键：`Ctrl+S` 保存、`Ctrl+N` 在工作目录内新建文件（简单流程，无自动补全）
- 后端新增 `save_working_file`（路径限制在 `working_dir` 内，与 `execute_file_operation` 同级校验）
- **联网（分阶段）**：
  - **Phase A（本变更）**：DeepSeek **Function Calling** — 定义 `search_web` 工具，后端执行检索并把结果回传模型（不发送 `web_search` 类型）
  - **Phase B（后续）**：可选 MCP 连接器架构，供高级用户接入 SerpAPI/Tavily 等（本变更仅设计预留，不实现完整 MCP 宿主）

## Capabilities

### New Capabilities

- `code-mode-editor`: 编程模式可编辑预览、编辑器设置、保存与快捷键、路径安全写盘
- `web-search`: 基于 Function Calling 的联网检索循环、配置项、与「联网搜索」技能的联动

### Modified Capabilities

（无既有规格需修改 `composer-toolbar` 等行为。）

## Impact

- **前端**：`web/index.html`（预览区结构）、`web/js/preview.js` 或新建 `web/js/code-editor.js`、`web/style.css`、`web/js/config.js` / 设置弹窗、`web/app.js`（快捷键）
- **后端**：`backend/main.py` / `backend/file_ops.py`（`save_working_file`）、`backend/api.py`（tool call 循环、`search_web` 执行器）
- **配置**：`config.example.json` 增加 `editor_word_wrap`、`web_search_provider`（可选 API Key 占位）
- **技能**：更新 `skills/web-search` 文案，与真实 function 行为一致
- **依赖（可选）**：轻量 HTTP 搜索（如 DuckDuckGo 无 key 方案）或用户配置的搜索 API Key
