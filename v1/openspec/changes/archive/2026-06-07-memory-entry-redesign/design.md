## Context

- **现状**：记忆系统用 `memory/items/{type}/{id}.json` 存碎片，每个 JSON 文件只有一句话 `content`。压缩时 LLM 输出 JSON 数组，一次产生 5-8 个碎片。FTS5 索引每个碎片为一行，检索返回 20 条碎片。
- **问题**：信息密度低、JSON 外壳浪费 token、碎片之间无关联、脱离上下文无叙事价值。
- **约束**：保留 FTS5 检索机制（加速搜索、降低 token）；不引入新依赖；旧数据兼容。

## Goals / Non-Goals

**Goals:**

- 每次压缩产出一篇完整 Markdown 文档（摘要 + 要点 + 关键词），替代 JSON 碎片
- YAML frontmatter 存元数据，Markdown body 存内容
- memory.md 改为索引文件，按日期列出所有 entry
- FTS5 索引粒度从"单个 item"改为"单篇 entry"
- 检索 2-3 篇完整 entry 替代 20 条碎片，token 预算不变但信息密度大幅提升
- 旧 JSON 碎片与新格式并存，自然淘汰

**Non-Goals:**

- 不做旧数据强制迁移
- 不改 docs/ 长文收藏系统
- 不改 FTS5 底层技术方案
- 不改配置字段结构

## Decisions

### 1. 新文件格式：YAML frontmatter + Markdown

每篇 entry 一个文件，路径：`memory/entries/{date}-{slug}.md`

```markdown
---
type: project
importance: 4
keywords: [群聊, 重命名, switch-toggle, UI优化]
related:
  - 2026-06-05-ui-refactor  # 都涉及 switch-toggle 组件
created_at: 2026-06-07
---

# 群聊功能增强

## 摘要
本次对话围绕 MeClaw 群聊模块进行了三项功能增强。在群聊列表中为每个群添加了重命名和删除按钮，hover 时显示，点击重命名弹出独立弹窗。删除群聊使用原生 confirm 确认，同时清除当前群状态。群设置弹窗用 switch-toggle 替代了原生 checkbox，三个数字输入改为带填充渐变的 range 滑块。

## 要点
- 群聊列表 hover 显示编辑/删除按钮，编辑弹窗支持回车确认
- 删除群聊后自动退出当前群会话，清除接话队列
- 群设置 toggle 统一用 switch-toggle 组件
- range 滑块通过 --range-pct CSS 变量实现渐变填充
- saveGroupSettings 兼容新旧两种 HTML 结构

## 关键词
群聊管理, 重命名, 删除群聊, switch-toggle, range-slider, 成员接话
```

**为什么一篇 entry 一个文件**：文件独立、易于管理和删除、FTS5 索引简单（一行对应一篇 entry）。

### 2. memory.md 改为索引

从存内容改为存索引，按日期列出所有 entry 的标题和一句话描述：

```markdown
# 长期记忆索引

- 2026-06-07 [群聊功能增强](entries/2026-06-07-群聊功能增强.md) — 群聊列表编辑/删除，设置弹窗重设计
- 2026-06-05 [记忆系统重构讨论](entries/2026-06-05-记忆系统重构.md) — 从碎片化 JSON 改为结构化 Markdown
```

**好处**：稳定层注入时 LLM 看到的是清晰的记忆目录，而不是散落的单句。每行约 30 token，1200 token 预算可容纳约 40 条索引。

### 3. FTS5 索引策略

索引结构新增 `memory_entries_index` 和 `memory_entries_fts` 表：

```sql
CREATE TABLE IF NOT EXISTS memory_entries_index (
    entry_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL UNIQUE,
    entry_type TEXT,
    importance INTEGER DEFAULT 3,
    created_at TEXT,
    file_mtime REAL DEFAULT 0,
    search_text TEXT,
    summary TEXT,
    keywords TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_entries_fts USING fts5(
    entry_id UNINDEXED,
    entry_type UNINDEXED,
    importance UNINDEXED,
    created_at UNINDEXED,
    search_text,
    tokenize='unicode61'
);
```

`search_text` = keywords + 摘要 + 要点拼接 + 中文 n-gram。旧 `memory_items_fts` 和 `memory_chunks_fts` 保留，兼容旧数据检索。

### 4. 检索结果格式化

旧：检索 20 条碎片，每条 50 token → 信息稀疏
新：检索 2-3 篇完整 entry，每篇 300-500 token → 信息自足

`format_memory_block` 输出格式：
```
## 相关记忆

1. [2026-06-07 群聊功能增强] 本次对话围绕 MeClaw 群聊模块进行了三项功能增强...
   要点：群聊列表编辑/删除、switch-toggle 组件、range 滑块渐变填充

2. [2026-06-05 记忆系统重构] 讨论了从碎片化 JSON 改为结构化 Markdown...
   要点：YAML frontmatter、memory.md 改为索引、FTS5 粒度调整
```

### 5. Entry 关联（related）

frontmatter 新增 `related` 字段，存储关联 entry 的文件名列表（不含路径和扩展名）：

```yaml
related:
  - 2026-06-05-ui-refactor
  - 2026-06-03-sidebar-redesign
```

**设计原则：**

- **不做双向写入**：A 引用 B 不代表 B 必须引用 A。关系是单向标注，由压缩时 LLM 判断
- **不做单独的关系图数据结构**：关系跟着 entry 走，删除 entry 时引用自然失效（指向的文件不存在就跳过）
- **不做单独的关系检索开关**：关系检索是记忆检索的一部分，关了记忆检索就自然关闭
- **不做专门的关系网搜索工具**：FTS5 关键词搜索已覆盖大部分场景

**检索时的行为：**

当 FTS5 命中一篇 entry 后，读取其 `related` 字段，尝试加载关联 entry 作为补充上下文。只要不超 token 预算，related entry 会追加到检索结果末尾。related entry 的排序权重低于直接 FTS 命中的 entry。

**LLM 标注 related 的 prompt 指引：**

在 extraction prompt 中增加一条规则："如果本次对话的内容与近期其他对话有明显的因果关系或并列关系，请在 related 字段中列出相关 entry 的文件名。没有关联则留空。"

### 6. Extraction Prompt 改动

旧 prompt 要求输出 JSON 数组，每个对象只有一句话。
新 prompt 要求输出单篇 Markdown 文档：

```
请从以下对话片段中写一篇记忆文档，包含：
1. 摘要（3-5 句话，概括整个对话的核心内容、讨论过程和结论）
2. 要点（3-8 条，从摘要中提取关键决策、代码改动、技术选型）
3. 关键词（5-10 个标签用于检索匹配）

输出格式（只输出 Markdown，不要其他文字）：
---
type: preference|fact|project|relationship
importance: 1-5
keywords: [关键词1, 关键词2, ...]
related: [关联entry文件名1, 关联entry文件名2]  # 可选，没有关联则留空
---

# 标题

## 摘要
...

## 要点
- ...

## 关键词
...
```

### 7. memory.md 维护逻辑变更

旧：压缩时自动追加一行事实（`append_memory_md_line`）
新：压缩时追加一条索引条目（日期 + 标题 + 一句话描述）

### 8. Token 预算重新分配

- 旧：1200 token 预算，检索 6-8 个碎片（每个 50-200 token），碎片化信息
- 新：1200 token 预算，检索 2-3 篇完整 entry（每篇 300-500 token），信息密度大幅提升
- memory.md 索引层：稳定注入，约 30 token/条，1200 token 可容纳 40 条索引

### 9. 旧数据兼容

- `memory/items/` 目录保留，旧 JSON 碎片不删除
- FTS5 检索同时查 `memory_entries_fts`（新）和 `memory_items_fts`（旧）
- 新压缩走新格式，旧记忆逐步自然淘汰
- 前端记忆面板可分别展示 entries 和 items

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| LLM 输出格式不稳定（Markdown 解析失败） | 严格 prompt + 容错解析（frontmatter 解析失败时用默认值） |
| 旧 items 和新 entries 检索结果重复 | 优先展示 entries，items 作为补充 |
| 单篇 entry token 量大，预算内只能放 2-3 篇 | 信息密度远高于碎片，2-3 篇足够覆盖上下文 |
| memory.md 索引过长 | 仅展示标题 + 一句话，40 条以内 |

## Migration Plan

1. 新建 `memory/entries/` 目录
2. SQLite 新增 `memory_entries_index` 和 `memory_entries_fts` 表
3. 新压缩走新格式写入 `entries/`
4. 旧 `items/` 保留，检索时兼容查询
5. memory.md 改为索引格式（旧内容保留，新追加走索引格式）
