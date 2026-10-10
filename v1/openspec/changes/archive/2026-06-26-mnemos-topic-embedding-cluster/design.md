## Context

P4 preference evolution 依赖 `topic_key` 对齐。当前 13 类 regex 无法覆盖开放域对话（如穿搭观察、诅咒宇宙设定等），导致 supersede 链断裂。Obsidian/Hermes 资料强调「关系与主题」比单条事实更重要。

## Goals / Non-Goals

**Goals:**

- Bot 级 topic registry：`topic_key` → centroid embedding + optional label
- 写入时 O(topics) 或 ANN 近邻分配（初期 topics 少，线性扫可接受）
- Regex 命中优先，保证已知 domain 稳定
- 支持 topic 合并候选（learner 后续消费，本提案只产候选）

**Non-Goals:**

- 跨 bot topic 共享
- 实时图谱 UI（wiki 模块独立）
- 自动删除 misc topic

## Decisions

1. **Regex-first, cluster-fallback**：已知 hint 命中则不改；否则 cluster。
2. **Centroid 更新**：同 topic 新原子写入后，centroid 做 running average（或 medoid 简化版）。
3. **新 topic 命名**：`topic_<short_hash>` + 可选 `label` 字段；UI 显示 label。
4. **阈值默认 0.85**：低于阈值开新 topic；可 per-bot 覆盖。
5. **Rebuild**：提供 `rebuild_topic_centroids` 管理命令，embedding 模型变更时重算。

## Risks / Trade-offs

- topic 爆炸（每句一个新 topic）→ 设 merge 候选 + consolidation 提案联动
- 英文题 + 多语言 embedding → 与 benchmark 环境一致即可
- 计算成本 → 仅写入时 embed 一次，查询侧无额外成本
