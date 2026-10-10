## Why

MeClaw 每次请求都会把 system prompt、记忆检索、摘要、群聊状态、编程文件上下文等拼进 API 消息；其中大量内容每轮变化，却放在稳定前缀位置，导致三方 API 的 Prompt Caching / KV 前缀复用几乎命不中，重复 prefill 最贵的一段 token。私聊、编程、群聊三种模式共用 `build_messages_for_api()`，需要在不改产品体验的前提下建立「稳定前缀 + 动态尾部」的上下文纪律，降低 token 成本并为进一步接入显式缓存与监控打基础。

## What Changes

- 新增 **上下文分层组装器**：将 API 消息拆为 `stable`（人设/固定规则/固定工具）、`semi_stable`（群成员表、项目概览 hash）、`dynamic`（时间、记忆检索、摘要、触发原因、read_files）三层，固定拼接顺序
- **清理 system 动态噪音**：当前时间、记忆检索块、会话摘要、群聊触发原因、编程 read_files 从早期 `system` 移到动态尾部（user message 前缀或尾部上下文块）
- **编程模式**：固定编程规则留在稳定 system；`working_dir`、项目概览、已读文件内容改为尾部注入；项目概览按目录 hash 复用
- **群聊模式**：群名/成员/@ 规则进半稳定块；触发原因、当前回复 Bot、用户 @ 列表进动态尾部；多 Bot 连发不污染稳定前缀
- **工具定义稳定化**：`search_web` 等 tools JSON 键序固定；非联网轮次不注入 tools
- **cache-safe 压缩**：`compress_context` 只追加摘要、不改写已有 system/tools/历史前缀
- **缓存监控（可选阶段）**：从 API usage 提取 cache 相关字段并记录命中率日志，为后续告警预留
- **不改动**：Bot 人设内容、souls/ 与 groups/ 记忆存储路径、前端对话交互流程

## Capabilities

### New Capabilities

- `context-cache-discipline`: 上下文分层组装、稳定前缀纪律、私聊/编程/群聊三模式动态块后移、工具序列化稳定、项目概览 hash 复用

### Modified Capabilities

- `compress-summary-detail`: 压缩后摘要注入位置改为动态尾部起始，禁止改写稳定前缀
- `bot-memory`: 记忆检索结果注入点从 system 前部改为动态尾部，检索逻辑与存储不变

## Impact

- **后端（核心）**：`backend/api.py`（`build_messages_for_api`、`build_system_prompt`、payload 构建）；新增 `backend/context_assembler.py`（或等价模块）
- **编程模式**：`backend/code_mode.py`（`ReadFilesManager.get_context_messages` 输出角色/位置调整；`generate_project_overview` hash 缓存）
- **联网**：`backend/web_search.py`（`get_current_time_context` 调用点迁移）
- **群聊**：`backend/api.py` 中 `_build_group_context_block` 拆分为稳定块与动态块
- **压缩**：`backend/main.py` 中 `compress_context` 与 `build_messages_for_api` 对齐 cache-safe 规则
- **配置**：`config.example.json` 可选增加 `prompt_cache_monitor_enabled`、模型最小可缓存 token 阈值（若接入显式缓存）
- **文档**：`docs/系统结构.md` 上下文数据流说明更新
- **无新运行时依赖**
