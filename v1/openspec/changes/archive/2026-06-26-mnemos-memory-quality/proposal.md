## Why

P1/P2 已换检索内核（真 embedding + 可选 rerank），P3 已按角色配模型。PersonaMem 200 题仍约 60%，主要短板在 **L1 原子质量**（重复噪声、无冲突消解、无重要性/衰减）与 **召回排序**（仅相关度，无巩固/遗忘曲线）。本提案在现有 topic-chain 演变能力之上，补齐「记忆质量层」，提升事实/推荐/演变分项命中率。

## What Changes

- L1 schema v3 扩展：`importance`、`hit_count`、`supersedes_id`；写入时同 topic 的 `switch` 自动链接 supersede。
- 写入侧 **embedding 近似去重**（相似度 > 阈值则合并/跳过，可配置）。
- 召回侧 **复合排序**：`α·rerank/hybrid + β·importance + γ·recency + δ·hit_boost`；召回后递增 `hit_count`（记忆巩固）。
- 过滤已被 supersede 的原子（软链，不删 L1 文件）。
- 增强 LLM 提取 prompt：结构化 JSON（含 topic_key / reason / supersedes 提示）。
- 配置项与默认零行为变化（权重默认使 composite ≈ 原 hybrid 排序）。

## Capabilities

### New Capabilities

- `mnemos-memory-quality`: L1 冲突消解、近似去重、重要性/衰减/巩固加权召回。

### Modified Capabilities

- `mnemos-memory-brain`: L1 写入与 hybrid 召回排序行为。

## Impact

- 后端：`store_l1.py`、`l1_extractor.py`、`memory_scoring.py`（新）、`hybrid.py`、`memory_brain.py`、`config_store.py`
- 索引：无需 schema bump（metadata 在 L1 frontmatter）
- 兼容：旧原子缺字段安全默认；回滚权重为 0 即恢复原排序
- 验证：PersonaMem official 200，关注 facts / recommendations / evolution 分项
