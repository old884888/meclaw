## Context

P1 让向量可生产、可缓存、可读取，但 `hybrid.py` 仍是「线性算分 + RRF 融合」，规模受 `SEMANTIC_SCAN_LIMIT=2000` 限制，且无精排。本提案补齐召回链路最关键的两块：**ANN 召回**（规模 + 速度 + 持久性）与 **Reranker 精排**（相关度 + 信噪比）。这是命中率从 ~58% 迈向 90%+ 的主战场。

## Goals / Non-Goals

**Goals:**

- 用 ANN 索引替换线性扫描，移除规模上限，支撑长期持久记忆。
- 两段式召回：候选并集（FTS + 向量）→ Reranker 精排 → 预算内 top-k。
- Reranker 可插拔（local cross-encoder / api LLM / off），可配置候选池与 top-k。
- 各级安全降级，且 `rerank_enabled:false`+ANN 关闭可回到 P1 行为。
- 精排后只注入高相关 top-k，命中率与省 token 兼得。

**Non-Goals:**

- 不改 L1 提取质量 / 冲突消解 / topic 聚类（留 P4）。
- 不做按角色配模型 UI（留 P3，本提案只加 rerank 必需配置）。
- 不替换 FTS（仍作为 lexical 候选来源）。

## Decisions

### D1：ANN 索引选型

倾向 **`sqlite-vec`**（与现有 SQLite 索引同进程、零额外服务、可随 `index.sqlite` 一起备份）；`faiss` 作为备选（更快但部署重）。两者都经一层 `VectorIndex` 抽象封装，便于切换与降级。

**为何不上独立向量服务（chroma server 等）**：违背本地优先、增加运维；嵌入式方案足够个人规模。

### D2：两段式召回编排

`before_chat` 召回改为：

1. FTS 候选（保留 `expand_memory_query`）
2. 向量候选（ANN，topN）
3. 并集去重 → `rerank_candidate_pool`（默认 ~20）
4. Reranker 打分（可关）→ 取 `rerank_top_k`（默认 ~5）
5. 预算内注入（沿用 token budget 与两阶段事实/链逻辑）

编排放 `memory_brain`，`hybrid` 只负责「产候选」，`rerank/` 负责「排候选」，职责清晰。

### D3：Reranker 可插拔

新增 `backend/domain/memory/rerank/`：

- `port.py`：`Reranker.score(query, candidates) -> scores` + `NullReranker`。
- `local.py`：cross-encoder（如 `bge-reranker-base`），懒加载单例，可选依赖。
- `api.py`：便宜 LLM 打分（批量 prompt 让模型对每条相关度打 0–1）。
- `factory.py`：按配置构造，失败回退 `NullReranker`（即融合序）。

### D4：配置

`rerank_enabled`(默认 false)、`rerank_provider`(`local`/`api`/`off`)、`rerank_model`、`rerank_candidate_pool`(默认 20)、`rerank_top_k`(默认 5)。ANN 开关复用 P1 的 `embedding_provider != off` 且索引存在即启用，必要时加 `ann_enabled`。

### D5：降级阶梯

`rerank(local/api)` 失败 → 融合序；`ANN` 失败 → P1 缓存向量线性算分；`embedding off` → 原哈希词袋/FTS。每层独立 try，互不阻断。

## Risks / Trade-offs

- [ANN 库为可选依赖，缺失] → `VectorIndex` 降级线性；文档标注安装方式；默认行为不依赖 ANN。
- [Reranker 增加延迟（尤其 api）] → 仅对小候选池（~20）打分；可关；local cross-encoder CPU 也快。
- [api rerank 增加费用] → 默认 off；候选池上限约束调用规模。
- [ANN 索引与 SQLite 一致性] → 写入即更新 + `rebuild_index` 全量重建兜底；identity 不一致触发重建。
- [top-k 太小漏召回] → 候选池/ top-k 可配；用 benchmark 调参（recall@k 与 accuracy 权衡）。

## Migration Plan

1. 依赖可选安装；默认 `rerank_enabled:false`、ANN 按可用性启用但有线性降级。
2. 合入后行为接近 P1；显式开启 rerank 才进入两段式精排。
3. 用 benchmark 逐项验证：仅 ANN、ANN+rerank(local)、ANN+rerank(api) 对比基线。
4. 回滚：关 rerank + 关 ANN（或 `embedding_provider:off`）回到 P1 / 原始行为。

## Open Questions

- `sqlite-vec` vs `faiss`：PoC 比较部署成本与召回质量后定。
- Reranker 默认模型（`bge-reranker-base` vs 更小）与是否提供 api 打分 prompt 模板默认值。
- `rerank_candidate_pool` / `rerank_top_k` 默认值需 benchmark 标定。
