# Tasks — prompt-cache-optimization

## 1. 上下文组装基础

- [x] 1.1 新增 `backend/context_assembler.py`：定义 `stable` / `semi_stable` / `dynamic` 三层数据结构与固定拼接顺序注释
- [x] 1.2 重构 `build_system_prompt()`：稳定层仅含 soul + skills + 固定文件/编程规则（移除路径、概览、时间）
- [x] 1.3 `build_messages_for_api()` 委托 `ContextAssembler`，输出 tools → stable → semi_stable → dynamic → history

## 2. 私聊与记忆

- [x] 2.1 记忆检索 `format_memory_block` 改注入 dynamic 层，不再追加早期 system
- [x] 2.2 `current_summary` 改注入 dynamic 层起始位置
- [x] 2.3 联网 `get_current_time_context()` 仅 dynamic 层注入，且仅在 `_wants_web_search` 时

## 3. 编程模式

- [x] 3.1 `_code_mode_prompt()` 拆分：固定规则留 stable；`working_dir` 与 overview 移出 stable
- [x] 3.2 实现项目目录 hash 缓存：hash 未变复用 session 内 overview 文本
- [x] 3.3 `ReadFilesManager.get_context_messages()` 改为返回 dynamic 文本块（非 early system），路径按 `read_order` 稳定排序

## 4. 群聊模式

- [x] 4.1 拆分 `_build_group_context_block()` 为 `build_group_stable_block()` 与 `build_group_dynamic_block()`
- [x] 4.2 semi_stable 含群名、成员、@ 规则；dynamic 含触发原因、reply_bot 身份、用户 @ 列表
- [x] 4.3 验证 `send_group_bot_reply` 连发时 stable/semi_stable 前缀一致、仅 dynamic 变化

## 5. 工具与 payload

- [x] 5.1 `SEARCH_WEB_TOOL` 与 payload 序列化使用稳定键序（`sort_keys=True` 或固定 dict）
- [x] 5.2 非联网请求确认不含 `tools` 字段；联网仅 tool 轮次带 tools

## 6. 压缩与监控

- [x] 6.1 确认 `compress_context()` 不修改 stable system / tools / 保留消息正文（仅删尾部消息）
- [x] 6.2 `calc_context_usage()` breakdown 对齐新分层（system / semi_stable / dynamic / messages）
- [x] 6.3 在 usage 日志中解析 cache 字段并输出命中率（字段缺失时静默跳过）

## 7. 文档与验收

- [x] 7.1 更新 `docs/系统结构.md` 上下文数据流说明
- [x] 7.2 手动验收：私聊多轮、编程 read_files、群聊 @ 连发、压缩后摘要、联网检索 — 行为不变且 API 消息前缀稳定
- [ ] 7.3 对比改造前后 API usage / 日志，记录一次命中率或 prompt_tokens 变化（需实机发消息、看 API 是否返回 cache 字段）
