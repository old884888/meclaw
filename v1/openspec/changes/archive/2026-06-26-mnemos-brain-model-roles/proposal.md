## Why

MNEMOS 目前只有「执行模型」与「后台模型（background）」两档，L1 提取、Tier3 摘要、embedding、rerank 都被迫共用同一个 background 模型或无处配置。不同任务对模型的要求差异很大：对话要强、提取要便宜、摘要要中等、embedding/rerank 要专用模型。本提案把「模型角色」从两档扩展为**按角色绑定**，让贵模型只用在该贵的地方，省钱且提质，并为 P1/P2 的 embedding / rerank 提供统一的配置入口。

## What Changes

- 引入**按角色配模型**：`executor`（对话）、`extraction`（L1 提取）、`summary`（Tier3 摘要）、`embedding`、`rerank`。
- 每个角色可绑定到某个 provider profile + model；**留空则继承回退链**（如 extraction/summary 回退 background → executor）。
- 全局默认 + **Bot 级覆盖**（沿用现有 `brains` 覆盖机制），与现有 UI「按脑配模型」诉求对齐。
- 后端「按角色解析模型」统一为一个解析器，替换现有零散的 `role="executor"/"background"` 逻辑（保持向后兼容）。
- embedding（P1）与 rerank（P2）的 `*_provider`/`*_model` 配置纳入同一「角色 → 模型」体系，避免配置碎片化。
- Bot 编辑器 UI 增加角色绑定区（最小可用），状态面板可展示各角色实际使用的模型。

## Capabilities

### New Capabilities

- `mnemos-brain-model-roles`: 按角色（executor/extraction/summary/embedding/rerank）绑定模型与回退链，支持全局默认与 Bot 级覆盖，并提供统一解析契约。

### Modified Capabilities

- `mnemos-multi-brain-orchestrator`: 后台任务（提取/摘要）与对话改为通过角色解析器取模型，而非固定 executor/background 二分。

## Impact

- 受影响后端：
  - `meclaw2/backend/storage/config_store.py`（角色字段归一、默认值、Bot 覆盖合并）
  - `meclaw2/backend/main.py`（`_profile_for_bot(role=...)` 扩展为按角色解析 + 回退链）
  - `meclaw2/backend/domain/memory/memory_brain.py` / `tier3_summarizer.py` / `l1_extractor.py`（取对应角色模型）
  - `meclaw2/backend/domain/brains/brain_status.py`（状态展示各角色模型）
- 受影响前端：
  - `meclaw2/web/index.html` / `app.js`（Bot 编辑器角色绑定 UI；状态面板模型展示）
- 兼容/回滚：未配置角色时回退到现有 background→executor 行为，**默认零行为变化**。
- 依赖：与 P1/P2 协同（embedding/rerank 角色复用本体系），但本提案可独立合入（这两个角色无对应实现时仅作配置占位）。
