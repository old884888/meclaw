## Why

MNEMOS（`meclaw2/`）当前聊天主链路仍是「system + 全量 history」直出，记忆层虽有 `MemoryService` 接口与 `LayeredMemoryService` 雏形，但未接入 WebSocket 生成流程。用户希望吸收 SuperBrain 设计思想，为每个 Bot 引入**多脑子协作**（执行脑、记忆脑、左脑、右脑、学习脑），优先把**个人对话体验**做到极致：长期记得住、长聊不断裂、每步有意义、不浪费 token、不让 AI 绕弯子。

## What Changes

- 在 `meclaw2/` 引入 **Bot 多脑子编排层（Multi-Brain Orchestrator）**，作为聊天前/后的统一调度入口。
- **执行脑（Executor）**：唯一对外接口；负责组 prompt、调 LLM、流式返回；只读记忆脑提供的摘要块，不直接写记忆。
- **记忆脑（Memory Brain）**：聊天前按需召回、聊天后异步写入、上下文压力时分级压缩（Snip / Prune / Summarize）；实现 L0–L3 个人对话记忆金字塔。
- **左脑（Left / Cognitive）**：任务拆解、约束核对、事实与逻辑补强；**仅在意图命中时激活**，默认不进入主链路。
- **右脑（Right / Persona）**：Soul、语气、关系感、情绪连续性；以**固定短摘要**注入，禁止每轮让模型自行发挥重写人格。
- **学习脑（Learner）**：离线定时任务；收集信号、整理画像候选、积累微调数据；**不参与实时回复**，不自动覆盖 Soul。
- 引入 **确定性意图路由 + Token 预算表**：系统决定激活哪些脑子、各块上限多少 token；模型不负责「要不要查十种记忆」。
- 将 `LayeredMemoryService` 重构并接入 `_save_user_message_and_prepare()` / `_run_generation()` 主链路。
- 新增个人对话记忆存储布局（`data/memory/`）、压缩决策缓存、软删除与审计。
- 设置页与记忆面板暴露多脑子开关、预算与水位线配置（可先只读展示状态）。

## Capabilities

### New Capabilities

- `mnemos-multi-brain-orchestrator`: 多脑子编排、意图路由、Token 预算、聊天主链路挂载点。
- `mnemos-memory-brain`: L0–L3 个人对话记忆、召回、写入、索引、软删除。
- `mnemos-context-compaction`: 四级水位线上下文压缩、保护区、单调替换缓存。
- `mnemos-learner-brain`: 离线学习信号收集、画像候选、定时整理（不阻塞聊天）。

### Modified Capabilities

- `meclaw2-memory-port`: 从 NoOp/未接线雏形扩展为 Multi-Brain 记忆脑实现，并定义各脑子与 `MemoryService` 的边界。

## Impact

- **主要目录**：`meclaw2/backend/main.py`、`meclaw2/backend/domain/memory/`、新增 `meclaw2/backend/domain/brains/`。
- **数据目录**：`meclaw2/data/memory/`（l0/l1/l2/l3、index.sqlite、replacement_cache）、扩展现有 `history/` 会话摘要字段。
- **配置**：`config.json` 增加多脑子开关、各层 token 预算、压缩水位线、学习脑调度配置。
- **前端**：聊天前可展示「本轮激活的脑子」与记忆注入量（调试/透明模式）；记忆管理面板（后续阶段）。
- **不影响**：MeClaw 1.0 `backend/` 主链路；现有供应商、Bot 大厅、会话 CRUD、流式协议保持兼容。
- **与知识库关系**：本变更**不以 Wiki/知识导入为主战场**；已有 `knowledge/` 模块可保留但默认不进入个人对话主链路，避免与记忆脑抢 token。

## Non-Goals

- 不在第一阶段引入 COS/S3、向量数据库、公网访问。
- 不让学习脑自动改写已生效的 Soul 或 system prompt（仅产出候选）。
- 不恢复 MeClaw 1.0 群聊、编程模式、技能系统。
- 不要求每轮对话激活全部五个脑子；未命中意图的脑子零 token 开销。
