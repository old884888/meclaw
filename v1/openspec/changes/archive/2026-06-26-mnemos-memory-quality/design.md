## Context

已有 `mnemos-preference-evolution`：topic_key / seq / polarity / reason + L3 时间线 + topic-chain 召回。仍缺：同 topic 显式 supersede 链、写入去重、召回时 importance/recency/hit_count 加权。Benchmark 显示 facts 与 recommendations 在 chain-first 注入下可能 regress，需用更干净的 L1 与 smarter ranking 修复。

## Goals / Non-Goals

**Goals:**
- 减少 L1 重复原子与过时偏好噪声。
- 同 topic 偏好切换时显式 `supersedes_id`，召回时优先最新、隐藏被取代项。
- 复合分数提升约束/高命中记忆的优先级。
- 默认配置下行为接近现状，便于灰度。

**Non-Goals:**
- LLM 全量重写 L1 历史。
- Topic embedding 聚类替代 regex（后续迭代）。
- 跨 Bot 记忆合并。

## Decisions

### D1：L1 frontmatter v3 字段

新增（均可选，读时默认）：
- `importance` (float 0–1)：constraint=1.0, preference=0.85, fact=0.7, todo=0.6；可手写覆盖。
- `hit_count` (int)：召回注入次数。
- `supersedes_id` (str)：本原子取代的原子 id。
- `superseded_by` (str)：被谁取代（双向便于过滤）。

**不写 v3 强制迁移**：`schema_version` 仍可为 2，新字段按需出现。

### D2：写入冲突消解

`write_atom` 后处理：
1. 若 `polarity==switch` 且 `topic_key` 已知，查同 topic 最新未 superseded 原子 → 设 `supersedes_id` + 反向 `superseded_by`。
2. 若 embedding 可用，与最近 N 条同 topic 比 cosine；≥ `memory_dedupe_threshold`（默认 0.92）→ 跳过写入或更新现有（v1：跳过并返回已有）。

### D3：复合召回分数

```text
final = w_rel * rel + w_imp * importance + w_rec * recency + w_hit * log1p(hit_count)
```

- `rel`：rerank score 归一化，或 hybrid_score。
- `recency`：指数衰减，`half_life_days` 默认 90；constraint 类型不衰减（floor=1）。
- 默认权重：`w_rel=1, w_imp=0.15, w_rec=0.1, w_hit=0.08`（可调，全 0 除 rel 即回退）。

### D4：召回后巩固

`before_chat` 注入成功后，对 shown atom ids 调用 `increment_hit_count`（best-effort，失败不阻断）。

### D5：LLM 提取增强

`extract_atoms_llm` prompt 要求 JSON 含 `type, content, topic_key?, reason?, supersedes_hint?`；映射到 write_atom 字段。

## Risks

- 去重阈值过高漏合并 / 过低误合并 → 默认保守 0.92，仅同 topic。
- 复合分数扰动 baseline → 默认权重小，单测 + benchmark gate。

## Migration

1. 部署写入/排序逻辑；新原子带新字段。
2. 可选 `rebuild_index`；旧原子 lazy enrich on read。
3. 回滚：config 权重置 0 + `memory_dedupe_threshold: 0` 关闭去重。
