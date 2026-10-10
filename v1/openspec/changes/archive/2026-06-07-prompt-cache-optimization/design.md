## Context

MeClaw 通过 `backend/api.py` 的 `build_messages_for_api()` 组装 OpenAI/DeepSeek 兼容的 `/chat/completions` 请求。当前顺序为：Bot system（soul + skills + 模式规则）→ 群聊 system → 当前时间 system → 记忆检索 system → 摘要 system → read_files system → 对话历史。

问题：时间戳、按 query 检索的记忆、群触发原因、项目概览、已读文件等**每轮或高频变化**的内容混在稳定前缀中，导致服务端 Prompt Caching / KV 前缀无法复用，重复 prefill 成本最高的一段 token。

三种模式共用同一组装入口：
- **私聊**：`bot_id` session，结构最简单，收益最大
- **编程**：`code` 模式注入 `working_dir`、项目概览、`read_files`
- **群聊**：`_build_group_context_block()` 含触发原因、当前回复 Bot、@ 列表

已有 `compress_context()` 会保留最近 1 轮并生成 `current_summary`，方向正确，但摘要仍作为早期 system 注入。

## Goals / Non-Goals

**Goals:**

- 建立「稳定前缀 + 半稳定块 + 动态尾部」三层上下文纪律
- 私聊 / 编程 / 群聊三模式统一由 `ContextAssembler` 输出 API messages
- 动态内容后移，不破坏模型可见信息（行为等价，仅注入位置变化）
- 工具 JSON 序列化稳定；非联网轮次不带 tools
- 压缩与记忆检索符合 cache-safe 规则
- 预留 cache usage 日志字段解析

**Non-Goals:**

- 本阶段不强制接入 Anthropic `cache_control`（取决于 profile provider 能力）
- 不改变 souls/、groups/ 记忆存储与检索算法
- 不改变前端对话 UI 与 @ 交互
- 不实现 Prometheus/Grafana 完整监控栈（仅后端日志埋点）

## Decisions

### 1. 新增 `ContextAssembler` 模块

**决策**：在 `backend/context_assembler.py` 集中分层，由 `build_messages_for_api()` 委托调用。

```text
Layer A — stable（字节级应尽量不变）
  tools（固定排序，仅联网首轮）
  system: soul + 固定 skills + 固定文件/编程规则（无路径、无概览、无时间）

Layer B — semi_stable（配置/项目变更时才变）
  群聊：群名 + 成员列表 + @ 格式说明（不含触发原因）
  编程：项目概览（hash 未变则复用缓存文本）

Layer C — dynamic（每轮追加，只放尾部）
  会话摘要 current_summary
  记忆检索块（原 search_memory 结果）
  群聊：触发原因 + 当前身份 + 用户 @ 列表
  编程：working_dir + read_files 内容
  联网：当前时间（仅 _wants_web_search 时）
  对话历史 messages
  本轮 user（动态块可前缀到 user content）
```

**备选**：继续在 `api.py` 内 if/else 拼装 → 拒绝，三模式逻辑会继续发散。

### 2. 动态块注入形式

**决策**：动态块优先合并为**单条 user 消息前缀**（`[上下文]\n...\n\n[用户]\n...`），而非多条早期 system。

- 对 OpenAI/DeepSeek 兼容接口，user 尾部变化不影响前面 system/tools 前缀匹配
- 群聊/编程的半稳定块仍可用 `system` 或 `user` 中靠后的一条「上下文说明」消息，但必须在 Layer B，且在历史消息之前

**备选**：全部改 `assistant` 上下文消息 → 拒绝，会污染对话历史语义。

### 3. 编程模式项目概览 hash

**决策**：`generate_project_overview(working_dir)` 结果附带目录结构 hash（文件路径 + mtime 或 size 摘要）。hash 不变则复用 session 内缓存的 overview 文本，避免每轮重扫磁盘改前缀。

overview 与 `working_dir` 路径从稳定 system 移除，放入 Layer B/C。

### 4. read_files 位置与顺序

**决策**：`ReadFilesManager.get_context_messages()` 不再返回 `role: system`；改为返回动态块文本，按 `read_order` 稳定排序后注入 Layer C。

文件内容仍受 `max_tokens` 预算裁剪（现有 `_trim` 逻辑保留）。

### 5. 群聊上下文拆分

**决策**：`_build_group_context_block()` 拆为：

| 函数 | 内容 | 层级 |
|------|------|------|
| `build_group_stable_block()` | 群名、成员、@ 规则、自动接话说明 | B |
| `build_group_dynamic_block()` | 触发原因、reply_bot 身份、用户 @ 列表 | C |

`_reply_bot_id` 切换只影响 C，不影响 A/B。

群聊补 @ 的 `_call_api_sync` 小请求保持独立短上下文，不写入主会话前缀。

### 6. 工具与 payload 稳定化

**决策**：
- `SEARCH_WEB_TOOL` 定义保持常量，序列化时 `sort_keys=True` 或固定 dict 顺序
- 仅联网分析首轮 `_chat_completion_once(tools=True)` 带 tools；最终流式轮 `tools=False`（现状保持）
- 非联网 Bot 请求 payload 不含 `tools` 键

### 7. cache-safe 压缩

**决策**：`compress_context()` 完成后：
- `current_summary` 更新方式不变
- `build_messages_for_api` 将摘要作为 Layer C 第一条动态块，**不**插入 Layer A system
- 禁止通过改写 `build_system_prompt()` 或修改历史消息内容来「压缩」

### 8. 监控（Phase 1 轻量）

**决策**：在 `_stream_chat_completion` / `_chat_completion_once` 解析 usage 时，若响应含 `prompt_cache_hit_tokens`、`cache_read_input_tokens` 等字段则记入 `_log`；计算 `hit_rate` 供调试。无字段则跳过，不报错。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 动态块改 user 前缀后模型对「系统约束」遵从度下降 | Layer A 保留完整人设与固定规则；动态块用明确 `[会话上下文]` 标题 |
| 部分 API 仅缓存连续相同前缀，user 前缀变化仍导致历史后段失效 | 这是预期；收益来自 A+B 稳定，长对话仍靠摘要压缩 |
| 项目 hash 遗漏文件变更 | hash 含 mtime；用户可 `new_task` 清 session 强制刷新 |
| 三方 API 不支持显式 cache 字段 | 纪律化上下文仍有服务端自动前缀缓存收益；监控字段可选 |
| 群聊半稳定块在改成员后失效 | 成员变更频率低，可接受一次 cache miss |

## Migration Plan

1. 实现 `ContextAssembler`，`build_messages_for_api` 切到新路径，保留旧逻辑开关 `use_legacy_context=False`（开发期，合并前删除）
2. 分模式验证：私聊 → 编程 → 群聊 → 联网
3. 对比压缩前后 `calc_context_usage` breakdown 与 API usage 日志
4. 更新 `docs/系统结构.md` 上下文数据流
5. 无 config 破坏性迁移；可选新增 `prompt_cache_log_enabled` 默认 true

**回滚**：恢复 `build_messages_for_api` 旧拼装顺序即可。

## Open Questions

- 当前主力 API（mimo / deepseek）是否返回 prompt cache usage 字段？实现后需实测一次
- 是否在 profile 级增加 `provider: anthropic` 以支持显式 `cache_control`（留作 follow-up change）
- 记忆检索放 user 前缀 vs 单独 `role: user` 上下文消息 — 实现时选一种并全模式统一
