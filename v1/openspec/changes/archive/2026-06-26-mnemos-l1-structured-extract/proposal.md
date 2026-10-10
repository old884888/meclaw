## Why

P4 已落地 polarity / supersede / embedding 去重，但 L1 提取仍是「截原话 + 薄 prompt」。PersonaMem 200 题仍在 ~60%，事实召回与演变链分项受限于原子结构不足：缺少 subject/predicate/object、实体归一与显式冲突标注。本提案把 L1 提取升级为结构化 LLM 输出，为后续 Topic 聚类与 Skill 提炼打基础。

## What Changes

- L1 LLM 提取输出结构化 JSON：`type`, `subject`, `predicate`, `object`, `polarity`, `confidence`, `topic_key`, `reason`, `supersedes_hint`
- 写入侧解析 JSON 并映射到 L1 frontmatter + 索引字段
- 保留启发式提取作为 fallback（LLM 失败或未配置 extraction 角色时）
- 增强 switch / supersede 链路：结构化 `supersedes_hint` 优先于 regex 推断
- 配置：`l1_extract_mode`（`heuristic` | `llm` | `hybrid`，默认 `hybrid`）

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `mnemos-memory-brain`: L1 atomic extraction SHALL support structured LLM output with schema validation and safe fallback.

## Impact

- 后端：`l1_extractor.py`, `store_l1.py`, `topic_metadata.py`, `memory_brain.py`
- 使用 P3 `extraction` 角色模型
- 兼容：旧 L1 原子无需迁移；新字段缺省安全默认
- 验证：PersonaMem 200 题 facts / evolution / recommendations 分项；对比 P4 baseline
