## 1. 配置与默认值

- [x] 1.1 在 `config_store.py` 的 `DEFAULT_CONFIG` 加入 `embedding_provider`（默认 `"off"`）与 `embedding_model`（默认 `""`）
- [x] 1.2 在 `normalize_config` 中归一 `embedding_provider`（限定 `local`/`api`/`off`）与 `embedding_model`
- [x] 1.3 单测：缺省值、非法 provider 归一为 `off`

## 2. Embedding 端口

- [x] 2.1 新建 `backend/domain/memory/embedding/__init__.py`
- [x] 2.2 `port.py`：定义 `EmbeddingPort`（`embed(texts) -> list[list[float]]`、`model_identity`、`available`）与 `NullEmbedding`
- [x] 2.3 `local.py`：本地实现，懒加载模型（onnx 或 sentence-transformers），进程内单例缓存，import/加载失败抛出可捕获异常
- [x] 2.4 `api.py`：复用 `adapters/providers.py` 调 embedding 接口；超时/报错抛出可捕获异常
- [x] 2.5 `factory.py`：按配置构造实现，任何失败回退 `NullEmbedding`
- [x] 2.6 单测：factory 选择逻辑 + 失败降级返回 NullEmbedding + NullEmbedding.available == False

## 3. 索引向量缓存

- [x] 3.1 `indexer.py` 给 `memory_index` 增加 `embedding`(BLOB) 与 `embedding_model`(TEXT) 列
- [x] 3.2 加入 schema 版本管理（`PRAGMA user_version` 或幂等 `ALTER TABLE ADD COLUMN`），旧库打开自动迁移
- [x] 3.3 实现 float32 向量 <-> BLOB 的紧凑序列化/反序列化工具
- [x] 3.4 `_upsert_record`：当 embeddings 启用时计算并写入向量与模型身份；`off` 时不写
- [x] 3.5 `list_indexed_records`：额外返回 `embedding`、`embedding_model`
- [x] 3.6 `rebuild_index`：能在模型身份变化时重算向量（identity 不一致则刷新）
- [x] 3.7 单测：加列迁移幂等、写入/读取往返、identity 记录正确

## 4. 检索改造（消费缓存向量）

- [x] 4.1 `hybrid.py` 注入/获取 EmbeddingPort（经 memory_brain 传入）
- [x] 4.2 `_semantic_hits`：端口可用时 embed(query) 一次，用缓存向量算 cosine；无兼容向量者按需补算或跳过
- [x] 4.3 端口不可用 / `off` 时保留原 `_text_to_vector` 哈希路径（行为等价）
- [x] 4.4 `memory_brain.py`：构造并向下传递 EmbeddingPort（依配置）
- [x] 4.5 单测：`off` 时与改造前召回等价；`local`(fake 端口) 时走缓存向量分支且不重算记录向量

## 5. 降级与健壮性

- [x] 5.1 端口构造失败、embed 抛错、缓存缺失/stale 三种路径均不抛、可继续聊天
- [x] 5.2 单测：模拟依赖缺失（local）与 API 报错，断言降级到 FTS/哈希且 `before_chat` 不抛

## 6. 依赖与文档

- [x] 6.1 本地推理依赖标记为**可选**（不进强制 requirements），新增可选安装说明
- [x] 6.2 更新 `meclaw2/docs/超级大脑增强路线.md` 标注 P1 已落地及如何开启（local/api/off）
- [x] 6.3 README / benchmark 文档补充：如何切换 `embedding_provider` 并 rebuild 索引

## 7. Benchmark 验证

- [ ] 7.1 用 `tests/benchmark/personamem` official 子集（≥200 题）跑 `off`（基线）与 `local`/`api` 对比
- [ ] 7.2 记录 accuracy / avg_recall_count / 延迟，确认 `off` 无回归、真 embedding 有增益
- [ ] 7.3 将对比结果回填到 `超级大脑增强路线.md` 第 7 节预期收益表
