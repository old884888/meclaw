## Why

`bot-multi-brain` 已在 MNEMOS 落地全局多脑子编排（执行/右脑/记忆/左脑/学习），但开关与 token 预算仍在全局 `config.json`，所有 Bot 共用一套策略。用户提出：多脑子配置应下沉到每个 Bot；后台任务（摘要、L1 提取）应可使用更便宜的模型，而不是与主对话共用同一模型。

## What Changes

- 在 `bots[]` 增加 **per-bot 多脑子配置** `brains` 对象，可覆盖全局默认值（开关、预算、压缩阈值、记忆策略）。
- 在 Bot 上增加 **`background_model`**（可选）：用于 Tier3 摘要、L1 提取、学习脑等后台 LLM 任务；为空时回退到 Bot 主 `model`。
- Bot 编辑弹窗新增 **「多脑子」分区**：各脑开关、token 预算、后台模型选择；全局设置页保留为「平台默认值」。
- 编排器读取配置时采用 **`merge(global, bot.brains)`**，Bot 未填字段继承全局。
- 后台 LLM 调用统一走 `resolve_bot_models(bot) -> {executor, background}`，避免五个脑五个模型。

## Capabilities

### New Capabilities

- `meclaw2-bot-brains`: per-bot 多脑子配置 schema、合并规则、Bot 编辑 UI、API 读写。

### Modified Capabilities

- `mnemos-multi-brain-orchestrator`: 从全局-only 改为 bot-scoped 配置解析。
- `mnemos-memory-brain`: L1 提取与 Tier3 摘要使用 `background_model`。
- `mnemos-context-compaction`: Tier3 摘要模型来源明确为 background。
- `meclaw2-memory-port`: Bot 字段扩展与默认值继承。

## Impact

- **后端**：`config_store.py`、`orchestrator.py`、`memory_brain.py`、`tier3_summarizer.py`、`l1_extractor.py`、`main.py` Bot CRUD。
- **前端**：`bot-editor` 多脑子区块；全局设置「多脑子」Tab 文案改为「默认模板」。
- **数据**：现有 `config.json` 向后兼容；旧 Bot 无 `brains` 字段时使用全局默认。
- **不影响**：MeClaw 1.0；已归档的 `bot-multi-brain` 实现逻辑保持，仅配置粒度下沉。

## Non-Goals

- 不为每个脑子单独绑定不同供应商（仅 executor + background 两档模型）。
- 不自动迁移全局设置到每个 Bot（Bot 留空即继承）。
- 不在本变更实现学习脑定时批处理 UI 审批流（仅保证 background 模型可用于已有候选生成路径）。
