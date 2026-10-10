## Why

当前记忆系统在压缩阶段让 LLM 输出 JSON 数组，每条记忆只有一句话的 `content`。一次压缩产生 5-8 个碎片文件，彼此无关联，信息密度极低。JSON 外壳（字段名、括号、引号）占每个文件 30-40% 的字符量，`source_session_id`、`confidence` 等字段在上下文之外毫无意义。FTS5 检索返回 20 条碎片，每条 ~50 token，但实际信息量不到 3 个完整段落。脱离原始上下文后，碎片化的记忆几乎没有叙事价值。

核心问题：**提取阶段就把信息拆碎了**。LLM 被要求输出 JSON 数组、每个对象只写一句话，自然产出就是高度压缩的碎片。

## What Changes

- **从"提取碎片"变为"写会议纪要"**：每次压缩不再输出 JSON 数组，而是输出一篇结构化 Markdown 文档
- **新文件格式**：YAML frontmatter + Markdown（摘要 + 要点 + 关键词），替代 JSON 碎片
- **存储路径变更**：`memory/entries/{date}-{slug}.md` 替代 `memory/items/{type}/{id}.json`
- **memory.md 角色变更**：从存内容改为存索引，按日期列出所有 entry 的标题和一句话描述
- **FTS5 索引粒度变更**：从"单个 item"改为"单篇 entry"，检索 2-3 篇完整 entry 替代检索 20 条碎片
- **Extraction prompt 重写**：要求 LLM 输出 Markdown 文档而非 JSON 数组
- **Entry 关联**：frontmatter 新增 `related` 字段，压缩时 LLM 可标注关联的 entry；检索命中时顺带拉 related entry 作为补充上下文
- **保留 FTS5 检索功能**：索引策略不变，仍用 SQLite FTS5 做全文检索，加速搜索、降低 token
- **旧数据兼容**：新旧格式并存，旧 JSON 碎片自然淘汰，不强制迁移

## Capabilities

### New Capabilities

- `memory-entry`: 结构化 Markdown 记忆条目（YAML frontmatter + 摘要 + 要点 + 关键词），一篇 entry 一个文件

### Modified Capabilities

- `bot-memory`: extraction 从 JSON 碎片改为单篇 Markdown；memory.md 从内容存储改为索引；检索粒度从碎片改为完整 entry

## Impact

- **后端**：`backend/memory/extractor.py`（prompt 重写、输出解析）、`backend/memory/store.py`（entry 读写函数）、`backend/memory/indexer.py`（索引粒度调整）、`backend/memory/retrieval.py`（检索结果格式化）
- **前端**：`web/js/memory.js`（记忆面板渲染适配新格式）
- **配置**：无新增配置项
- **数据**：`souls/{bot-id}/memory/entries/` 新目录；旧 `items/` 目录保留兼容
- **依赖**：无新增依赖
