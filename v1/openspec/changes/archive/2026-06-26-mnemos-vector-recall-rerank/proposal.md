## Why

P1（`mnemos-embedding-port`）提供了真向量与缓存地基，但召回排序仍是线性扫描 + RRF 融合，**没有近似最近邻（ANN）索引**也**没有精排（reranker）**：规模一大检索变慢，且「谁在多个列表靠前」不等于「和问题最相关」。要把命中率从 ~58% 推向 90%+，需要在召回后加一层精排，并用 ANN 支撑大规模持久记忆。

## What Changes

- 引入 **ANN 向量索引**（如 `sqlite-vec` / `faiss`），替换 `_semantic_hits` 的全表线性扫描，去除 `SEMANTIC_SCAN_LIMIT=2000` 的静默截断，支撑长期持久记忆。
- 新增 **Reranker 精排阶段**：召回（FTS + 向量）并集取 top-N（如 20）→ reranker 打分 → 注入 top-k（如 3–5）。
- Reranker 可插拔：**cross-encoder 本地模型** 或 **便宜 LLM 打分**，可配置、可关闭。
- 新增配置：`rerank_enabled`、`rerank_provider`（`local` / `api` / `off`）、`rerank_model`、`rerank_candidate_pool`、`rerank_top_k`。
- 召回链路保持安全降级：ANN/Reranker 不可用时退回 P1 的缓存向量线性打分，再退回 FTS/哈希。
- 精排后**只注入高相关 top-k**，在提升命中率的同时减少注入 token（信噪比优化）。

## Capabilities

### New Capabilities

- `mnemos-vector-recall`: ANN 向量召回能力——索引构建/更新、近邻查询、规模上限移除、与 FTS 候选的并集策略。
- `mnemos-rerank`: 可插拔精排能力——候选池、打分来源（本地 cross-encoder / API LLM）、top-k 截断、降级。

### Modified Capabilities

- `mnemos-memory-brain`: `before_chat` 召回流程改为「召回 → 精排 → 预算内 top-k 注入」，并定义各级降级行为。

## Impact

- 受影响后端：
  - `meclaw2/backend/domain/memory/hybrid.py`（召回融合 → 召回+精排两段式）
  - `meclaw2/backend/domain/memory/indexer.py`（ANN 索引构建/查询，或新增向量索引模块）
  - 新增 `meclaw2/backend/domain/memory/rerank/`（port + local + api）
  - `meclaw2/backend/domain/memory/memory_brain.py`（编排召回→精排→注入）
  - `meclaw2/backend/storage/config_store.py`（rerank/ANN 相关配置归一）
- 依赖：ANN 库与 cross-encoder 为**可选安装**，缺失降级。
- 数据：可能引入向量索引文件 / 表；可由 `rebuild_index` 重建。
- 兼容/回滚：`rerank_enabled: false` + ANN 关闭即回到 P1 行为；P1 的 `embedding_provider: off` 仍可彻底回退到原始哈希词袋。
- 依赖 P1 已合入（向量已可生产与缓存）。
