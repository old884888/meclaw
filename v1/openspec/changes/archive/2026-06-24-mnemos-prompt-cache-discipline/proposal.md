## Why

MNEMOS（`meclaw2/`）的对话主链路通过 `MultiBrainOrchestrator.prepare_turn()` 组装 API 消息，当前顺序是：`system_base → persona → memory → cognitive → 会话摘要 → 历史消息 → 压缩`。其中 **persona 之后的记忆检索块、认知块、会话摘要都是按本轮 query 变化的内容，却被放在历史消息之前的 system 位置**，导致三方 API（DeepSeek / Anthropic 等）的 Prompt Caching / KV 前缀复用几乎命不中，每轮都重复 prefill 最贵的一段 token。

1.0（`backend/`）已经用 `context-cache-discipline`（`backend/context_assembler.py`）解决了同一问题：**稳定前缀 + 半稳定块 + 动态尾部** 三层纪律，并在 `_log_cache_usage()` 里解析命中率。2.0 尚未移植这套纪律，也没有把缓存命中率暴露给用户——用户无法判断当前供应商是否真的命中了缓存、token 成本是否被优化。

本变更将 1.0 的上下文缓存纪律移植进 2.0 多脑子编排，并在已有的「超级大脑状态」体系（顶栏胶囊、composer 轻状态、详情面板）中新增 **缓存命中率** 展示。

## What Changes

- **新增上下文分层组装纪律**：在 `orchestrator.prepare_turn()` 内将消息拆成 `stable`（system_base + persona）、`semi_stable`（预留：未来项目概览/群成员）、`dynamic`（memory + cognitive + 会话摘要 + 时间）三层；动态块合并为单段，前缀到最后一条 user 消息，而非插在历史之前的 system。
- **稳定 payload 序列化**：provider 请求体序列化使用确定性键序（对齐 1.0 `sort_keys=True`），避免键序抖动破坏前缀匹配。
- **采集缓存 usage**：`providers.stream_chat()` / `chat_once()` 解析流式结尾或响应中的 `prompt_cache_hit_tokens` / `cache_read_input_tokens` / `cache_creation_input_tokens`，计算 `hit_rate`，字段缺失时静默跳过。
- **回传命中率**：通过 WebSocket 新增 `cache_usage` 事件（或并入现有 `brain_trace`），把本轮 read/create/hit_rate 发给前端。
- **UI 展示**：在 composer 轻状态（`#usage-hint`）追加「缓存命中 X%」；在大脑状态详情面板「上下文」分区展示最近一轮缓存读取/创建/命中率；供应商不返回 cache 字段时显示「不支持」而非报错。
- **cache-safe 压缩复核**：确认 `compact_for_api` 只调整历史/摘要，不改写 stable 前缀。

## Capabilities

### New Capabilities

- `mnemos-context-cache-discipline`: 2.0 多脑子编排的稳定前缀 + 动态尾部组装纪律、确定性 payload 序列化、缓存 usage 采集与命中率计算。

### Modified Capabilities

- `mnemos-multi-brain-orchestrator`: `prepare_turn()` 输出遵循稳定前缀纪律，动态块后移；trace 增加缓存 usage 字段。
- `meclaw2-super-brain-status`: composer 轻状态与详情面板新增缓存命中率展示，WebSocket 消费 `cache_usage`。

## Impact

- **后端**：
  - `meclaw2/backend/domain/brains/orchestrator.py`：分层组装、动态块前缀到 user。
  - `meclaw2/backend/adapters/providers.py`：确定性序列化、解析 usage cache 字段。
  - `meclaw2/backend/main.py`：WebSocket 推送 `cache_usage`；状态 API 暴露最近一轮缓存指标。
  - `meclaw2/backend/domain/brains/brain_status.py`：`context` 分区补充缓存字段。
- **前端**：
  - `meclaw2/web/app.js`：`updateUsageHint()` 追加命中率；详情面板「上下文」分区渲染缓存指标；WebSocket 处理 `cache_usage`。
  - `meclaw2/web/index.html` / `style.css`：必要的展示位与样式。
- **数据**：不迁移历史数据；不改记忆存储与检索算法。
- **测试**：新增组装顺序单测（动态块在历史之后、stable 不含 query 派生内容）、usage 解析单测；扩展多脑子 smoke。

## Non-Goals

- 不强制接入 Anthropic 显式 `cache_control`（取决于 provider 能力，作为后续可选项）。
- 不做缓存命中率的长期趋势图或历史聚合，仅展示最近一轮 / 当前会话。
- 不改变 souls/、memory 存储布局与检索算法。
- 不改变前端对话交互与五脑激活逻辑。
