## Why

MNEMOS 当前的「语义」检索其实是 SHA1 哈希词袋（`hybrid._text_to_vector`），本质只是词的精确重叠，无法处理同义/改写/上下位词，PersonaMem official 50 题命中率被卡在 ~58%。要把「大海捞针」推向主流 90%+，第一步是引入**真正的向量嵌入**作为可复用基础设施。本提案只做「地基」——可插拔的 Embedding 接口与向量入库缓存，不破坏现有 FTS 路径，可独立合入与回滚。

## What Changes

- 新增可插拔 **EmbeddingPort** 抽象：`embed(texts) -> vectors`，统一向量来源。
- 提供两个实现，运行时按配置二选一：
  - **本地小模型**（默认，符合本地优先）：如 `bge-small-zh` / `multilingual-e5-small`，CPU 可跑。
  - **Embedding API**：复用现有供应商体系，新增 embedding 模型角色。
- 新增配置项：`embedding_provider`（`local` / `api` / `off`）与 `embedding_model`；缺省安全回退。
- **向量入库缓存**：写 L1 时计算并持久化 embedding（扩展 `memory_index`），查询侧只对 query 计算一次，消除每轮对至多 2000 条记录的 O(N) 重算。
- 本地模型与向量库依赖**可选安装**：依赖缺失或加载失败时自动降级为现有哈希词袋/FTS 行为，不阻断聊天。
- **本提案不改变检索排序算法本身**（ANN + Reranker 精排留给后续提案 P2）；仅保证 embedding 可被生产、缓存、读取。

## Capabilities

### New Capabilities

- `mnemos-embedding-port`: 可插拔向量嵌入端口，定义 embedding 的来源选择（本地/API/关闭）、降级策略、向量缓存与读取契约。

### Modified Capabilities

- `mnemos-memory-brain`: L1 写入时附带生成并持久化向量；检索的语义分支改为优先消费缓存向量（行为等价回退保证不破坏现有召回）。

## Impact

- 受影响后端：
  - `meclaw2/backend/domain/memory/hybrid.py`（语义分支改为消费缓存向量 + 端口）
  - `meclaw2/backend/domain/memory/indexer.py`（`memory_index` 增加向量列 / 旁表，schema 版本管理）
  - `meclaw2/backend/domain/memory/l1_extractor.py`（写 L1 时触发向量生成）
  - `meclaw2/backend/domain/memory/memory_brain.py`（注入 EmbeddingPort）
  - 新增 `meclaw2/backend/domain/memory/embedding/`（port + local + api 实现）
  - `meclaw2/backend/storage/config_store.py`（`embedding_provider` / `embedding_model` 归一与默认值）
- 依赖：本地实现引入可选依赖（如 `sentence-transformers` / `onnxruntime` 或等价轻量方案）；缺失时降级。
- 数据：索引 schema 版本 bump；旧索引可重建（已有 `rebuild_index`），旧 L1 原子缺向量时按需补算。
- 兼容/回滚：`memory_retrieval_strategy` 仍可切回 `fts`；`embedding_provider: off` 完全退回当前哈希词袋行为。
- 不影响 prefix cache 纪律（embedding 属离线/检索期计算，不进入对话 prompt 稳定前缀）。
