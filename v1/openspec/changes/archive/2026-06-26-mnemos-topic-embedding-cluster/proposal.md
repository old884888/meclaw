## Why

当前 `topic_key` 依赖 `TOPIC_KEY_HINTS` 硬编码正则，命不中则落入 `misc_<hash>`，偏好演变链（evolution）在 PersonaMem 上仍是短板。P4 已有同 topic supersede，但 topic 划分本身不准。本提案用 embedding 聚类 / 近邻分配替代（或增强）正则 topic，让任意话题都能形成可追踪的演变链。

## What Changes

- 新增 Topic 聚类服务：对新 L1 原子计算 embedding，与已有 topic centroid 比相似度
- 相似度 > 阈值 → 归入已有 topic；否则创建新 topic（可读 label 由 LLM 或首条 content 摘要生成）
- 保留 `TOPIC_KEY_HINTS` 作为优先规则（regex 命中则跳过聚类）
- 配置：`topic_cluster_enabled`, `topic_cluster_threshold`（默认 0.85）
- 索引扩展：topic centroid 向量缓存（per bot）

## Capabilities

### New Capabilities

- `mnemos-topic-cluster`: Embedding-based topic assignment and centroid maintenance for L1 atoms.

### Modified Capabilities

- `mnemos-memory-brain`: L1 write path SHALL assign topic keys via regex-first, cluster-fallback strategy.

## Impact

- 后端：`topic_metadata.py`（新 cluster 模块）、`store_l1.py`、`indexer.py`
- 依赖 P1 embedding port（已有）
- 验证：PersonaMem evolution / reasons 分项；topic 链可视化（memory browser 可选）
