## Context

当前 `extract_atoms_llm()` 使用薄 prompt，输出自由文本后再启发式切分。P4 已在写入侧支持 `polarity`、`supersedes_id`、embedding 去重，但输入质量仍是瓶颈。Hermes/知识工程资料强调：经验要结构化，才能冲突消解与演变链对齐。

## Goals / Non-Goals

**Goals:**

- 定义稳定的 L1 提取 JSON schema，一次 LLM 调用产出 0–N 条原子
- 结构化字段驱动 supersede、topic_key、importance 默认值
- LLM 失败时零回归：回退 heuristic 路径
- 提取结果可审计（保留 raw LLM JSON 于 L0 或 debug 字段）

**Non-Goals:**

- Topic embedding 聚类（见 `mnemos-topic-embedding-cluster`）
- Skill 层（见 `mnemos-skill-memory`）
- 自动改 soul.md

## Decisions

1. **Schema 优先于长 prompt**：固定 JSON array，每条 atom 必填 `content` + `type`；其余可选。
2. **hybrid 默认**：先 heuristic 快速提取约束/偏好信号，LLM 仅在有 extraction 模型且 turn 含可记忆内容时运行。
3. **supersedes_hint**：允许 LLM 返回 `supersedes_content` 或 `supersedes_id`；写入侧用 embedding 模糊匹配同 topic 旧原子。
4. **实体归一轻量版**：subject/object 存原文 + `normalized` 可选字段；不做外部 NER 服务。
5. **成本**：使用 extraction 角色 + `max_tokens` 上限；单 turn 最多 N 条原子（默认 5）。

## Risks / Trade-offs

- LLM JSON 解析失败 → fallback heuristic，记录 warning
- 英文 benchmark + 中文提取模型可能不一致 → 允许 per-bot extraction 模型配置（已有 P3）
- 结构化字段增多 → frontmatter 变大；L1 文件仍 Markdown，索引只存必要列
