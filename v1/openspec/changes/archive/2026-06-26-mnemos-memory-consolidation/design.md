## Context

当前系统擅长「写入 + 召回」，弱于「长期整理」。L3 画像会堆叠；同 topic 多条近似 L1 仍独立存在；`_update_l2_summary` 非 LLM 真摘要。资料中 MEMORY.md 2200 字符上限 + 80% 强制合并，是低成本高 ROI 的模式。

## Goals / Non-Goals

**Goals:**

- 可配置的容量阈值与 consolidation 动作
- merge：同 topic embedding 相似 + 非 pinned → 合并为一条，保留 supersede 链
- compress：topic 链 > N 条 → 生成 chain summary 节点
- archive：marked archived，不参与 recall 注入，文件保留审计
- 全异步，learner 可消费 merge 候选（可选）

**Non-Goals:**

- 物理删除 L1 文件（默认 archive 软标记）
- 自动改 soul
- GEPA 式优化

## Decisions

1. **Job 触发**：post-turn 检查 + 定时兜底；超阈值才跑。
2. **LLM 可选**：merge/compress 可用 summary 角色；heuristic 合并作为 fallback。
3. **Pin 规则**：`type=constraint` 或 `importance >= 0.9` 不 archive。
4. **L3 阈值**：字符或 token 估算，超 80% 触发 LLM 压缩（复用 tier3 summarizer 模式）。
5. **Trace**：brain status 展示 last consolidation run。

## Risks / Trade-offs

- 过度 merge 丢细节 → 保留 L0 证据链 + merge 审计 log
- LLM 成本 → 仅超阈值触发，默认关或 conservative 阈值
