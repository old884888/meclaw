## Why

MeClaw 1.0 以 pywebview 进程内桥接 (`pywebview.api`) 粘合 Python 与 Web 前端，功能持续堆叠后呈现：**前后端紧耦合、难以 Web/多端复用、模块边界模糊、记忆/群聊/编程模式缠在一起**。产品需要一次 **MeClaw 2.0** 重建：先交付**可日常使用的最小闭环**（本地存储、多 Bot、API 配置、流式对话），再按路线图叠加记忆、群聊等能力。

本次变更 **不替换 1.0 运行中的代码**，而是在独立目录 `meclaw2/` 新建 2.0 工程，1.0 继续维护直至 2.0 MVP 可切换。

## What Changes

### 2.0 MVP（本变更实现范围）

- **新工程 `meclaw2/`**：Python FastAPI + WebSocket 后端，Web 前端，本地数据目录
- **本地存储**：`config.json`、`history/`、`souls/` 落盘，重启不丢
- **多 Bot**：创建 / 编辑 / 删除 / 切换；每 Bot 绑定供应商与可选模型覆盖
- **灵魂**：读取 `soul.md`（+ 可选 `constraints.md`）注入 system prompt
- **API 供应商**：多 Profile（url、key、model、provider）；测试连接
- **基础对话**：发消息、流式回复、停止生成、多轮历史
- **会话**：每 Bot 多会话；新建 / 切换 / 删除 / 列表
- **UI 壳**：桌面三栏布局简化版（Bot 侧栏 + 对话区 + 设置入口），暗色主题
- **记忆预留**：`MemoryService` 接口 + NoOp 实现 + 目录占位；**不实现检索/写入**

### 明确不在 MVP

- 记忆检索、压缩提取、记忆库 UI
- 群聊、@ 接话链
- 编程模式、文件树、附件
- 联网搜索、技能、专家模式
- 上下文压缩（可仅提示「会话过长请新建」）
- 1.0 数据自动迁移工具（可后续独立变更）

### 与 1.0 关系

- **BREAKING**（对 2.0 而言）：通信从 `pywebview.api` 改为 HTTP + WebSocket；目录为 `meclaw2/` 独立根
- 1.0 代码路径 **不删除**，并行存在

## Capabilities

### New Capabilities

- `meclaw2-platform`: 2.0 工程结构、本地部署、前后端分离、数据目录约定、启动方式
- `meclaw2-ui-shell`: 主界面布局、导航层级、视觉与交互（侧栏 / 顶栏 / 对话区 / 设置）
- `meclaw2-providers`: API 供应商 Profile CRUD、测试连接、与 Bot 绑定
- `meclaw2-bots`: 多 Bot CRUD、灵魂文件夹、`soul.md` 加载与编辑入口
- `meclaw2-sessions`: 按 Bot 隔离的会话索引与消息持久化
- `meclaw2-chat`: 流式对话、停止、上下文组装（不含记忆块）
- `meclaw2-memory-port`: 记忆服务抽象接口、NoOp 实现、配置占位与扩展点

### Modified Capabilities

- （无：2.0 为全新能力集，不修改 `openspec/specs/` 下 1.0 既有规格）

## Impact

- **新增目录**：`meclaw2/`（backend、web、data 或沿用项目根数据约定）
- **依赖新增**：`fastapi`、`uvicorn`、`websockets`（与 1.0 `requirements.txt` 分离，见 `meclaw2/requirements.txt`）
- **文档**：`openspec/changes/meclaw-2-mvp/` 设计产物；可选 `docs/meclaw2/` 用户向说明（实现阶段）
- **不影响**：现有 `backend/`、`web/`、`main.py` 启动路径直至用户主动切换

## 产品优先级（闭环验收）

| 优先级 | 能力 | 验收 |
|--------|------|------|
| P0 | 本地存储 + 启动 | 重启后配置与会话仍在 |
| P0 | API 配置 + 测试连接 | 供应商可用 |
| P0 | 多 Bot + soul | ≥2 Bot 风格可区分 |
| P0 | 流式对话 | 能聊、能停 |
| P0 | 会话切换 | 每 Bot 多会话正确隔离 |
| P1 | 简单用量提示 | 消息条数或粗算 token |
| P2+ | 记忆 / 群聊 / 编程等 | 后续变更，仅接口预留 |
