## 1. 配置

- [x] 1.1 `config_store.py` 新增 `rerank_enabled`(默认 false)、`rerank_provider`(`local`/`api`/`off`)、`rerank_model`、`rerank_candidate_pool`(默认 20)、`rerank_top_k`(默认 5)
- [x] 1.2 （如需）新增 `ann_enabled` 或以 `embedding_provider!=off && 索引存在` 推导启用
- [x] 1.3 `normalize_config` 归一与边界校验；单测

## 2. ANN 向量索引

- [x] 2.1 定义 `VectorIndex` 抽象（add/update/query/rebuild/available）
- [x] 2.2 `sqlite-vec` 实现（首选）；构造/查询失败可降级
- [x] 2.3 写 L1 时更新 ANN 索引；`rebuild_index` 支持全量重建（identity 一致）
- [x] 2.4 移除 `_semantic_hits` 的 `SEMANTIC_SCAN_LIMIT` 硬截断（ANN 路径）
- [x] 2.5 单测：大于旧上限的记录可被召回；ANN 不可用降级线性

## 3. Reranker

- [x] 3.1 新建 `backend/domain/memory/rerank/`：`port.py`（`Reranker.score` + `NullReranker`）
- [x] 3.2 `local.py`：cross-encoder 懒加载单例（可选依赖）
- [x] 3.3 `api.py`：便宜 LLM 批量打分（prompt 模板 + 解析）
- [x] 3.4 `factory.py`：按配置构造，失败回退 NullReranker
- [x] 3.5 单测：factory 选择 + 失败降级 + NullReranker 返回融合序

## 4. 两段式召回编排

- [x] 4.1 `hybrid.py`：产出 FTS + 向量候选并集去重，限 `rerank_candidate_pool`
- [x] 4.2 `memory_brain.py`：候选 → Reranker 打分 → `rerank_top_k` → 预算内注入（沿用事实/链两阶段）
- [x] 4.3 各级降级：rerank 失败→融合序；ANN 失败→缓存向量线性；embedding off→哈希/FTS
- [x] 4.4 单测：rerank 开/关注入差异；降级路径不抛；预算约束生效

## 5. Benchmark 与调参

- [ ] 5.1 official ≥200 题对比：基线(P1) / 仅ANN / ANN+rerank(local) / ANN+rerank(api)
- [ ] 5.2 标定 `rerank_candidate_pool`、`rerank_top_k` 默认值（recall@k vs accuracy）
- [ ] 5.3 记录命中率与注入 token 变化，确认「命中率↑且 token↓」

## 6. 依赖与文档

- [x] 6.1 ANN 库与 cross-encoder 标记可选安装；缺失降级说明
- [x] 6.2 更新 `超级大脑增强路线.md`：P2 落地、开启方式、调参结论
- [x] 6.3 README/benchmark 文档补充 rerank 与 ANN 切换说明
