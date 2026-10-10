## Context

MNEMOS 对话主链路：`main.py::_build_api_messages()` → `MultiBrainOrchestrator.prepare_turn()` 组装 OpenAI/Anthropic 兼容 messages → `providers.stream_chat()` 流式调用。

当前 `prepare_turn()`（`orchestrator.py`）追加顺序：

```text
[system] system_base
[system] persona_block         # 相对稳定
[system] memory_block          # 按 query 检索 → 每轮变
[system] cognitive_block       # 按 query → 每轮变
[system] 会话摘要               # 随对话增长变
... 历史 user/assistant ...
→ compact_for_api()
```

问题：`memory_block` / `cognitive_block` / 摘要都在历史之前的 system 段，且每轮内容变化，破坏了服务端前缀缓存。1.0 已在 `backend/context_assembler.py` 用三层纪律解决，主规格见 `openspec/specs/context-cache-discipline/spec.md`。

`providers.stream_chat()`（`providers.py`）目前只 `yield` 文本 token，丢弃流式结尾的 `usage`；`build_payload()` 用 `requests.post(json=payload)`，未固定键序。

UI 侧 `app.js::updateUsageHint()` 已渲染「上下文 % · Tier · 记忆召回」，`brain_status.py` 的 `context` 分区已有 `ratio / compact_tier`，是缓存命中率的天然落点。

## Goals / Non-Goals

**Goals:**

- 2.0 组装遵循「stable → semi_stable → history → dynamic 尾部」纪律，行为等价（模型可见信息不变，仅位置变）。
- 动态块（memory/cognitive/摘要/时间）合并后前缀到最后一条 user，不再作为历史前的 system。
- provider payload 确定性序列化。
- 采集并计算缓存命中率，经 WebSocket 回传，UI 展示。

**Non-Goals:**

- 不接入 Anthropic 显式 `cache_control`。
- 不做命中率历史趋势/图表。
- 不改记忆检索算法与存储布局。

## Decisions

### 1. 复用 1.0 的 `context_assembler` 思路，2.0 内落地

**决策**：在 `meclaw2/backend/domain/brains/` 下新增 `context_assembler.py`（移植 1.0 等价逻辑：`join_blocks` / `build_dynamic_context` / `prefix_user_content` / `assemble_api_messages`），由 `prepare_turn()` 调用。

新组装顺序：

```text
Layer A stable:      [system] system_base + persona（拼成稳定 system，尽量字节不变）
Layer B semi_stable: [system] 预留（项目概览 / 群成员；2.0 暂空，结构保留）
            history:  历史 user/assistant
Layer C dynamic:     memory + cognitive + 会话摘要 + 当前时间
                      → 合并为 "[Session context]\n..." 前缀到最后一条 user.content
```

- persona 归入 stable：persona 随 Bot 固定，归稳定前缀收益最大。
- memory/cognitive/摘要归 dynamic：每轮变，后移到 user 前缀。
- `prepare_turn()` 仍输出 `brain_trace`（activated/tokens 不变），仅调整消息位置。

**理由**：与 1.0 纪律一致，可直接复用主规格 `context-cache-discipline`；trace token 统计逻辑保留。

### 2. dynamic 块注入位置

**决策**：动态文本前缀到「最后一条 user 消息」的正文（`prefix_user_content`），多模态时前缀到第一个 text part；若无 user 消息则追加一条仅含上下文的 user。与 1.0 完全一致。

**权衡**：user 尾部变化不影响前面 system 前缀匹配；代价是模型对「系统约束」遵从略降——通过 stable 层保留完整 persona、dynamic 用明确 `[Session context]` 标题缓解。

### 3. 确定性 payload 序列化

**决策**：`providers.py` 发送前对 payload 用 `json.dumps(payload, ensure_ascii=False, sort_keys=True)` 并以 data 形式 POST（对齐 1.0 `_post_chat_json`），替代 `requests.post(json=...)`。Anthropic / generic 分支统一处理。

### 4. 采集缓存 usage

**决策**：在 SSE 解析中捕获 usage：

- OpenAI/DeepSeek：末尾 chunk 或 `usage` 字段含 `prompt_cache_hit_tokens`、`prompt_cache_miss_tokens`；部分实现用 `cache_read_input_tokens`。
- Anthropic：`message_start` / `message_delta` 的 `usage` 含 `cache_read_input_tokens`、`cache_creation_input_tokens`。

`stream_chat()` 增加可选回调或改为 yield 结构化事件，把解析到的 usage 透出。计算：

```text
cache_read   = cache_read_input_tokens | prompt_cache_hit_tokens | 0
cache_create = cache_creation_input_tokens | prompt_cache_miss_tokens | 0
hit_rate     = round(cache_read / (cache_read + cache_create) * 100, 1)  # 分母为 0 → None
```

字段全缺 → 返回 `None`（UI 显示「不支持」），不报错。

**实现注意**：当前 `stream_chat()` 是纯文本生成器。为最小侵入，新增 `last_usage` 收集（如通过传入的 mutable dict 或在 `main.py` 流式循环里解析），避免大改调用方。

### 5. WebSocket 回传

**决策**：生成结束后（`onStreamDone` 之前/同时）发送：

```json
{ "event": "cache_usage", "generation_id": "...",
  "cache_read": 12000, "cache_create": 800, "hit_rate": 93.8, "supported": true }
```

`supported=false` 表示供应商未返回字段。前端按 `generation_id` 关联当前会话。

### 6. 状态 API 与 UI

**决策**：
- `brain_status.py` 的 `context` 分区追加 `cache`：`{ read, create, hit_rate, supported, updated_at }`，取最近一轮（runtime 内存，best-effort，重启重置）。
- `app.js::updateUsageHint()` 在召回之后追加「缓存命中 X%」（`supported=false` 时省略或显示「缓存 —」）。
- 详情面板「上下文」分区展示 read/create/hit_rate。

### 7. cache-safe 压缩

**决策**：复核 `compact_for_api()`，确保压缩仅作用于历史/摘要尾部，不改写 stable system 前缀；如有改写 system 的路径则调整为只动 dynamic/history。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 动态块移到 user 前缀后模型对系统约束遵从下降 | stable 层保留完整 persona + system_base；dynamic 用 `[Session context]` 明确标题 |
| 部分 API 仅缓存连续相同前缀，user 前缀变化仍使历史后段失效 | 预期行为；收益来自 A 段稳定，长对话仍靠压缩 |
| 三方 API 不返回 cache 字段 | UI 显示「不支持」，纪律化前缀仍有服务端自动缓存收益 |
| `stream_chat()` 改造影响群聊/专家等其他调用方 | 用可选回调/收集器，默认不改变 yield 文本契约 |
| 摘要后移导致与现有 `[会话摘要]` 注入重复 | 统一由 dynamic 注入，移除 orchestrator 中历史前的摘要 system |

## Migration Notes

- 无数据迁移。
- 行为对用户透明：回复内容不变，仅 token 成本与命中率展示变化。
- 可分阶段上线：先做「采集 + 展示」（不动组装也能看到当前命中情况），再落地分层组装提升命中率。
