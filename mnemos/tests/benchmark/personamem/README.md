# PersonaMem 记忆 Benchmark（MNEMOS）

两套评测：

| 套件 | 命令 | 说明 |
|------|------|------|
| **B：中文 Lite** | `--suite lite` | 10 道中文 MCQ，测偏好/演变/隐式/干扰等 |
| **A：官方 32k 子集** | `--suite official` | PersonaMem 官方 `questions_32k.csv` + `shared_contexts_32k.jsonl` |
| 离线冒烟 | `--suite mini` | 2 道英文样例，无需下载 HF |

四种模式：

| 模式 | 含义 | 适合场景 |
|------|------|----------|
| `memory`（默认） | 对话 replay 写入 L0/L1，答题时**只用检索块** | 主评测 |
| `baseline` | 不写记忆，只用最近 N 条消息 (`--baseline-messages`, 默认 8) | 低 baseline |
| `rag_messages` | 不写 L1，直接从原始对话中检索语义相关消息 | 无记忆化 RAG baseline |
| `full_context` | 把原始对话截入 prompt（`--full-context-strategy head/tail`，默认 head） | 理论上限 |

> **注意**：official PersonaMem 数据集没有 `recall_keywords`，benchmark 会显示 `storage_hit_rate: n/a (no keywords)`，请以 **accuracy** 和 **avg_recall_count** 为主要指标。50 题结果噪声较大，200+ 题才适合做强对比。

## 快速开始

### 1. 中文 Lite（推荐先跑，无需下载）

只测**检索命中率**（不调 LLM）：

```powershell
py -3 meclaw2/tests/benchmark/personamem/eval_mcq.py --suite lite --dry-run
```

完整 MCQ（需 `meclaw2/data/config.json` 里配置 API）：

```powershell
py -3 meclaw2/tests/benchmark/personamem/eval_mcq.py --suite lite --mode memory --profile-id p_xxxx
```

对比 baseline 和 rag_messages：

```powershell
py -3 meclaw2/tests/benchmark/personamem/eval_mcq.py --suite lite --mode baseline --profile-id p_xxxx
py -3 meclaw2/tests/benchmark/personamem/eval_mcq.py --suite lite --mode rag_messages --profile-id p_xxxx
```

### 2. 官方 PersonaMem 32k（档 A）

下载数据（约几十 MB，来自 HuggingFace）：

```powershell
py -3 meclaw2/tests/benchmark/personamem/download_data.py
```

跑前 50 题（memory 模式，单行命令）：

```powershell
py -3 meclaw2/tests/benchmark/personamem/eval_mcq.py --suite official --limit 50 --mode memory --profile-id p_xxxx --output meclaw2/tests/benchmark/personamem/data/report_memory_50.json
```

对比四种模式（200 题以上才稳定）：

```powershell
py -3 meclaw2/tests/benchmark/personamem/eval_mcq.py --suite official --limit 200 --mode memory --profile-id p_xxxx --output data/memory_200.json
py -3 meclaw2/tests/benchmark/personamem/eval_mcq.py --suite official --limit 200 --mode baseline --profile-id p_xxxx --output data/baseline_200.json
py -3 meclaw2/tests/benchmark/personamem/eval_mcq.py --suite official --limit 200 --mode rag_messages --profile-id p_xxxx --output data/rag_200.json
py -3 meclaw2/tests/benchmark/personamem/eval_mcq.py --suite official --limit 200 --mode full_context --full-context-strategy tail --profile-id p_xxxx --output data/fc_tail_200.json
```

> 50 题随机噪声大（±5–8%），请以 200+ 题作为正式对比。

### 3. 自动化冒烟（CI 友好）

```bash
py -3 meclaw2/tests/test_personamem_benchmark_smoke.py
```

## 指标说明

- **accuracy**：MCQ 选对比例（需 API，`--dry-run` 时不计算）
- **storage_hit_rate**：关键偏好是否已写入 L1 原子记忆
- **retrieval_hit_rate**：答题时检索块 / FTS / 已存 L1 中能否找到关键偏好
- **avg_recall_count**：`before_chat` 检索块中的 `-` 条目数均值

## 记忆检索策略（FTS vs Hybrid）

MNEMOS Memory brain 通过 `memory_retrieval_strategy` 控制 `before_chat` 检索方式（`meclaw2/data/config.json` 或 bot 级 `brains` 覆盖）：

| 策略 | 行为 | 适用场景 |
|------|------|----------|
| `fts` | 仅 SQLite FTS 关键词匹配 | 可解释、低误召回；查询与 L1 用词高度重叠时有效 |
| `hybrid`（默认） | FTS + 本地轻量语义相似度（RRF 融合）+ 确定性 query expansion | PersonaMem 类「语义个性化」题，查询与存储偏好无精确词重叠 |

**Query expansion** 会在检索前（不注入 prompt）根据问题意图追加如「偏好 / 过敏 / 推荐 / 旅行 / 饮食」等词，提高 L1/L2 命中率。

**回滚方式：**

1. 设 `memory_retrieval_strategy` 为 `"fts"` 恢复纯 FTS 行为
2. 或设 `memory_retrieval_enabled: false` 关闭记忆注入

### 真 Embedding（P1，可选）

`config.json` 新增字段（默认 `off`，合入后零行为变化）：

```json
{
  "embedding_provider": "off",
  "embedding_model": "",
  "embedding_profile_id": ""
}
```

| `embedding_provider` | 行为 |
|----------------------|------|
| `off` | 沿用哈希词袋语义分支（默认） |
| `local` | 本地 fastembed 模型（需 `pip install -r requirements-embedding.txt`） |
| `api` | 调用供应商 OpenAI 兼容 `/embeddings` 接口 |

开启 local 后建议 **rebuild 索引**（或在 Bot 设置里触发索引重建），让 L1 原子写入缓存向量：

```json
"embedding_provider": "local",
"embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

Benchmark 仍支持环境变量桥接（配置为 off / rerank_enabled false 时）：

```powershell
$env:MNEMOS_EMBED="local"
$env:MNEMOS_RERANK="local"
```

**Production 配置（推荐）** — 在 `config.json`：

```json
"embedding_provider": "local",
"embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
"ann_enabled": true,
"rerank_enabled": true,
"rerank_provider": "local",
"rerank_model": "BAAI/bge-reranker-base",
"rerank_candidate_pool": 20,
"rerank_top_k": 5
```

| 字段 | 默认 | 说明 |
|------|------|------|
| `ann_enabled` | true | embedding 开启时用全量向量扫描（无 2000 条截断） |
| `rerank_enabled` | false | 开启后：候选池 → cross-encoder 精排 → top-k 注入 |
| `rerank_candidate_pool` | 20 | FTS+向量并集上限 |
| `rerank_top_k` | 5 | 精排后注入条数上限 |

对比报告：`py -3 meclaw2/tests/benchmark/personamem/compare_reports.py base.json new.json`

PersonaMem official 50 题（memory 模式）hybrid 改造前后参考：

| 指标 | 改造前（FTS-only 行为） | 改造后（hybrid 默认） |
|------|-------------------------|------------------------|
| accuracy | ~48% | **58%** |
| avg_recall_count | 0 | **11.0** |

## 提取策略

- `--extract heuristic`（默认）：零 LLM 成本，用规则写 L1
- `--extract llm`：每轮调用 background 模型做 L1 提取（更准，更贵）

## 参考

- [PersonaMem GitHub](https://github.com/bowen-upenn/PersonaMem)
- [PersonaMem 数据集](https://huggingface.co/datasets/bowen-upenn/PersonaMem)
