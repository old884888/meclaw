## Context

路线图 §10 明确：记忆仿海马体，Skill 仿「怎么做」。当前所有经验压入 L1 原子，流程性知识被拆碎。资料中 Hermes L3 Skills 层 + 渐进加载 + Curator 版本管理，是我们 P6 轻量版的目标形态。

## Goals / Non-Goals

**Goals:**

- Skill 与 L1 分离的数据模型与目录布局
- 复用 P1/P2 embedding + rerank 做 skill 检索
- Task intent 路由（复用 cognitive router 或轻量规则）决定是否查 skill
- Approve 流程：API approve candidate → write skill file
- supersede 版本链（复用 L1 模式）

**Non-Goals:**

- 跨 bot skill 市场
- 自动 approve
- GEPA 进化
- MCP / 工具调用绑定（later）

## Decisions

1. **文件格式**：Markdown + YAML frontmatter（与 L1 一致，人机可读）。
2. **Index**：SQLite 表或扩展现有 memory index；字段：skill_id, embedding, status, topic_tags。
3. **Injection 位置**：动态 user-prefix 块 `[相关技能]`，遵守 prefix cache 纪律。
4. **Budget**：`skill_token_budget`（默认 400），top-1 skill 优先。
5. **Intent**：关键词 + cognitive brain 路由；MVP 规则：含「怎么做」「步骤」「教程」「帮我写」等。

## Risks / Trade-offs

- Skill 与 L1 重复 → 写入时 dedupe hint，consolidation 联动
- Token 膨胀 → 严格 budget + 单 skill 默认
- 低质量 draft → 必须 approved 才注入
