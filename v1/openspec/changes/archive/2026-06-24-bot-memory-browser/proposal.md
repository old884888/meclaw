## Why

MNEMOS 已在后台持续写入 L0 证据、L1 原子记忆、L2 会话摘要、L3 用户画像，并在超级大脑状态面板中展示各层数量。但用户无法查看具体内容，导致：

- 不知道 L1「原子」里到底记了什么。
- 不知道 L2 摘要是否准确、来自哪次会话。
- 不知道 L3 画像是否已生成、内容是什么。
- 无法判断记忆系统是否真正在工作，只能看到「0 条 / N 条」计数。
- 后端已有 `GET /memory/l1`、`GET /memory/l3`、`DELETE /memory/l1/{id}`，但前端没有统一入口；L0/L2 列表 API 缺失。

因此需要一个 **Bot 记忆库浏览器**，让用户按 Bot 查看、搜索、删除（L1）记忆内容，并与现有超级大脑状态面板形成「统计 → 详情」闭环。

## What Changes

- 新增 **记忆库抽屉/弹层**，按 Bot 展示 L0/L1/L2/L3 四个 Tab。
- 从超级大脑状态面板的「记忆层级」区域进入（点击 L0/L1/L2 计数或「查看记忆库」按钮）。
- 补全后端只读列表 API：L0 证据、L2 会话摘要、记忆搜索（复用现有 `search_memory`）。
- L1 原子：列表 + 类型徽章 + 软删除（复用现有 DELETE API）。
- L3 画像：只读 Markdown 预览（第一版不可编辑）。
- 空状态、分页/懒加载、删除后刷新状态计数。

## Capabilities

### New Capabilities

- `meclaw2-memory-browser`: Bot 记忆库 UI、Tab 切换、搜索、L1 删除、从状态面板入口。

### Modified Capabilities

- `mnemos-memory-brain`: 新增 L0/L2 列表与 search API；统一 list 响应 schema。
- `meclaw2-super-brain-status`: 记忆层级区块可点击，打开记忆库并传递当前 Bot/session 上下文。

## Impact

- **后端**：
  - `meclaw2/backend/main.py`: 新增 `GET /memory/l0`、`GET /memory/l2`、`GET /memory/search`。
  - 复用 `store_l0`、`store_l2`、`indexer.search_memory`。
- **前端**：
  - `index.html`: 记忆库 modal/drawer 结构。
  - `app.js`: `openMemoryBrowser()`、Tab 渲染、L1 删除、搜索。
  - `style.css`: 记忆列表、type 徽章、空状态。
- **数据**：只读为主；L1 删除沿用现有软删审计。
- **测试**：API smoke（L0/L2/search）、前端 smoke（打开抽屉、空 Bot）。

## Non-Goals

- 不在第一版编辑 L3 画像或 L2 摘要正文。
- 不做 L0 删除或批量清理。
- 不做记忆版本 diff 或审计详情 UI（`deleted/audit.jsonl` 仅后端保留）。
- 不在 Bot 编辑器内加第二个入口（可后续迭代）；第一版入口以状态面板为主。
