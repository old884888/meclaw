## Context

MNEMOS 的混合检索（`hybrid.py`）语义分支用 `_text_to_vector` 把分词哈希进 256 维词袋（hashing trick），不是真正的语义嵌入；它只能捕捉词的精确重叠，靠 `INTENT_EXPANSIONS` 硬编码同义词兜底。`_semantic_hits` 每次查询对至多 `SEMANTIC_SCAN_LIMIT=2000` 条记录**实时重算向量**，既慢又在记忆超 2000 条后静默截断。

当前索引层 `indexer.py` 维护 `memory_index`（结构化字段 + mtime）与 `memory_fts`（FTS5）。本提案在此之上引入**可插拔 Embedding 端口**与**向量入库缓存**，作为后续「ANN + Reranker 精排」（P2）和「按角色配模型」（P3）的地基。

约束：本地优先、可回滚、不破坏 prefix cache 纪律、旧数据向后兼容。

## Goals / Non-Goals

**Goals:**

- 定义统一的 `EmbeddingPort.embed(texts) -> vectors` 接口，本地与 API 两实现可运行时切换。
- 写 L1 时计算并持久化向量；检索仅 embed 一次 query，复用缓存向量。
- 任意失败（依赖缺失 / 模型加载失败 / API 报错）均安全降级为现有哈希词袋 / FTS 行为。
- 记录 embedding 模型身份，支持索引重建时识别并刷新过期向量。
- `embedding_provider: off` 完全等价于当前行为（可回滚基线）。

**Non-Goals:**

- 不引入 ANN 向量库 / 近似最近邻索引（留 P2）。
- 不改变融合/排序算法本身、不加 Reranker（留 P2）。
- 不做「按脑/按任务配模型」的完整 UI（留 P3；本提案只加 embedding 必需的最小配置）。
- 不改 L1 提取的内容质量 / 冲突消解（留 P4）。

## Decisions

### D1：端口抽象 `EmbeddingPort`

新增 `backend/domain/memory/embedding/` 包：

- `port.py`：`EmbeddingPort` 协议 + `NullEmbedding`（`off` 时返回「不支持」）。
- `local.py`：本地实现，懒加载模型（如 `sentence-transformers` 的 `bge-small-zh` / `multilingual-e5-small`），首次使用时加载并缓存实例。
- `api.py`：复用现有 provider 体系（`adapters/providers.py`）调用 embedding 接口。
- `factory.py`：依据 `embedding_provider` / `embedding_model` 选择实现；任何构造失败返回 `NullEmbedding`。

**为何用协议而非继承**：与现有 `MemoryScope` / 端口风格一致，便于测试注入 fake。

**模型身份（model identity）**：用 `f"{provider}:{model}:{dim}"` 字符串标识，写入向量缓存，便于检测 stale。

### D2：向量缓存存储方式

在 `memory_index` 增加两列：`embedding`（BLOB，float32 紧凑字节）与 `embedding_model`（TEXT）。

- 选择**同表加列**而非旁表：L1 与向量一一对应，复用现有 `_upsert_record` 写入路径，事务简单。
- 通过 `PRAGMA user_version` 或建表时 `IF NOT EXISTS` + 迁移检查实现 **schema 版本管理**；旧库打开时若无列则 `ALTER TABLE ADD COLUMN`。
- 检索时 `list_indexed_records` 额外取出 `embedding` / `embedding_model`，由 hybrid 语义分支消费。

**备选**：独立 `sqlite-vec` 旁表。**不选**的原因：那是 P2（ANN）的范畴；本提案只做「缓存 + 线性打分复用」，加列最小侵入。

### D3：检索改造（最小变更）

`hybrid._semantic_hits` 增加分支：

- 若端口可用（非 Null）：embed(query) 一次；对候选用**缓存向量**算 cosine；无兼容缓存向量者按需补算或跳过。
- 若端口不可用 / `off`：走原 `_text_to_vector` 哈希路径（**保持现状**）。

线性扫描仍在（P2 才换 ANN），但**不再每条重算向量**，延迟主要降在此处。

### D4：写入触发

`l1_extractor` 写原子并 `index_atom` 后，由 indexer 在 `_upsert_record` 内（embeddings enabled 时）计算并写入向量。集中在 indexer 一处，避免提取路径散落调用。

### D5：配置与默认值

`config_store` 归一新增：

- `embedding_provider`：默认 `off`（**首版默认关闭**，保证零行为变化，显式开启才生效）。
- `embedding_model`：默认空字符串。
- API 模式复用 provider profile；具体「embedding 角色绑定 provider」最小化：先支持指向某个 profile + model 名。

### D6：依赖可选

本地实现的重依赖（如 `sentence-transformers` / `onnxruntime`）**不写进强制 `requirements.txt`**，改为可选安装说明 + 运行时 `try import`；缺失即降级。避免给纯 API / off 用户强加几百 MB 依赖。

## Risks / Trade-offs

- [本地模型体积/首次加载慢] → 懒加载 + 进程内单例缓存；文档标注可选安装；默认 `off` 不影响现有用户。
- [线性扫描仍 O(N)] → 本提案只解决「重算」开销；规模问题明确留给 P2 的 ANN，避免一次改太多。
- [向量列把索引文件撑大] → float32 + 小维度（384/512）单条约 1.5–2KB，可接受；提供 rebuild 重新生成。
- [模型身份不一致导致分数错配] → 缓存写入 `embedding_model`；不兼容则补算或排除，绝不混分。
- [API embedding 增加费用/延迟] → 仅写入与 query 时调用；失败降级；默认 `off`。
- [schema 迁移出错] → 用 `ADD COLUMN` 幂等迁移 + 版本号；最坏情况 `rebuild_index` 全量重建（已有能力）。

## Migration Plan

1. 加列与版本管理：打开旧库自动 `ALTER TABLE ADD COLUMN`（幂等）。
2. 默认 `embedding_provider: off`，合入后**零行为变化**。
3. 用户显式设为 `local`/`api` 并（可选）`rebuild_index` 后，向量逐步补齐；未补齐者按需补算或走 FTS。
4. 回滚：设回 `off` 即恢复原哈希词袋行为；向量列保留不影响 FTS。

## Open Questions

- 本地模型首选 `bge-small-zh-v1.5` 还是 `multilingual-e5-small`？（建议 PoC 用 benchmark 二选一，先不写死）
- 本地推理后端用 `sentence-transformers` 还是 `onnxruntime`（更轻、无 torch）？倾向 onnx，PoC 验证。
- 向量维度与归一化策略是否需在配置暴露，还是由模型身份隐含固定？（倾向后者，减少误配）
