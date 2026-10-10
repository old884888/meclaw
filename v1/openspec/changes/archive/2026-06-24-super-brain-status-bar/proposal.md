## Why

MNEMOS 已经具备多脑子编排、Bot 级多脑子配置、后台模型、L0-L3 记忆、上下文压缩和 `brain_trace` 调试事件。但这些能力目前分散在设置页、Bot 编辑器、后台存储和 WebSocket 事件里，用户无法在日常对话中直观看到：

- 当前 Bot 的“超级 AI 大脑”是否健康。
- 本轮到底激活了哪些脑子。
- 记忆是否开启、召回了多少、L0/L1/L2/L3 是否存在。
- 上下文压力是否接近压缩阈值。
- 后台模型是否在处理 L1 提取或 Tier3 摘要。
- Bot 使用的是平台默认配置还是 Bot 级覆盖配置。

因此需要一个可常驻但不打扰聊天的 **超级 AI 大脑状态栏**，把关键状态压缩成一行，并提供可展开详情面板用于解释功能逻辑、记忆状态和单轮流程。

## What Changes

- 在顶栏新增 **大脑状态胶囊**，展示当前 Bot 的总体健康、记忆状态、上下文比例、后台任务状态。
- 在聊天输入区现有 usage hint 附近补充会话级状态，例如 `上下文 33% · Tier0 · 记忆召回 5 · 后台空闲`。
- 新增 **超级大脑状态详情面板**，展示：
  - 当前 Bot 与模型：供应商、主模型、后台模型、配置来源。
  - 各脑区：执行脑、右脑、记忆脑、左脑、学习脑的启用/激活/降级/错误状态。
  - 记忆层：L0/L1/L2/L3 统计、最近写入、索引状态、最近错误。
  - 上下文：估算 token、最大上下文、使用率、压缩 tier、Tier3 摘要状态。
  - 后台任务：L1 提取、Tier3 摘要、学习脑信号的最近状态。
  - 本轮 trace：最近一次 `brain_trace` 的激活脑区与 token 使用。
- 新增后端状态 API：按 Bot / 当前会话返回状态栏需要的聚合数据。
- 扩展 `brain_trace` 结构，使 UI 可以稳定消费，而不是仅作为调试日志。
- 对记忆存储提供轻量统计接口，不扫描超大原文内容。

## Capabilities

### New Capabilities

- `meclaw2-super-brain-status`: 顶栏状态胶囊、聊天区轻状态、详情面板、状态加载与 WebSocket trace 更新。

### Modified Capabilities

- `mnemos-multi-brain-orchestrator`: 提供更结构化、UI 可消费的 trace 与上下文压缩指标。
- `mnemos-memory-brain`: 提供 L0/L1/L2/L3 层级统计、最近写入、索引状态和错误摘要。
- `meclaw2-bot-brains`: 将 Bot 级 effective brains / 模型解析结果纳入状态 API 与 UI 展示。

## Impact

- **后端**：
  - `meclaw2/backend/main.py`: 新增 `/api/bots/{bot_id}/brain/status`。
  - `orchestrator.py`: 输出稳定 trace schema。
  - `memory_brain.py` / memory stores: 提供统计 helper。
  - 可选：后台任务状态记录到内存或轻量状态文件。
- **前端**：
  - `index.html`: 顶栏状态胶囊、状态详情 modal/drawer。
  - `app.js`: 状态加载、渲染、WebSocket `brain_trace` 合并。
  - `style.css`: 胶囊、脑区状态点、详情面板样式。
- **数据**：
  - 不迁移历史数据。
  - 状态 API 只读现有配置、history、souls/memory 与最近 runtime 状态。
- **测试**：
  - 新增状态 API smoke。
  - 新增 trace schema 与记忆统计 helper 单元测试。

## Non-Goals

- 不在第一版实现完整记忆管理面板（删除、编辑、审计详情仍留给后续）。
- 不做实时后台任务队列系统；第一版只展示最近状态与当前运行状态。
- 不把状态栏变成可编辑设置页；设置仍在 Bot 编辑器与设置页里完成。
- 不强制每次聊天都打开 `brain_trace_enabled`；状态栏可消费最近 trace，但不要求调试事件默认开启。
