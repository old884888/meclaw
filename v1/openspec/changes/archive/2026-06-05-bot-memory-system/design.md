## Context

- **现状**：MeClaw 用 `history/{session_id}.json` + `current_summary` 承担短期上下文；`souls/{id}/memory.md` 整文件进 system prompt，AI 可通过 `write_memory_file` 写入；`soul.md` / `knowledge/` 承担人设与静态知识。主聊天链路为云端 API（DeepSeek 等）+ 流式 + Function Calling 联网，挂载点在 `build_messages_for_api()`。
- **问题**：记忆与长文收藏未分离；`memory.md` 易膨胀；无按问题检索；用户期望「每类一个文件夹 + 工具搜索」，而非整库塞进 prompt。
- **约束**：pywebview 桌面应用、PyInstaller 打包友好；不引入 mem-llm/Ollama/向量库；不替换 `send_message` 主链路；沿用 `souls/` 目录。

## Goals / Non-Goals

**Goals:**

- 一 Bot 一目录：`souls/{id}/memory/`，按内容分类子文件夹（人类可读）
- 一 Bot 一索引：`memory/index.sqlite`，FTS5 加速检索（**双写：文件夹为真源，sqlite 为搜索层**）
- 三层分工：稳定事实（`memory.md`）/ 可检索中期记忆（`items/`）/ 长文收藏（`docs/`）
- 发消息前 **工具程序 `search_memory()`** 检索 + token 预算注入；不扫描全目录进 prompt
- 压缩上下文双管线：会话摘要 + 记忆提取；**顺便自动维护 `memory.md`**（importance≥4 稳定 fact/preference）
- 全局与 per-bot 开关

**Non-Goals:**

- 短期记忆层（已有 history + summary）
- 向量数据库、embedding 服务、mem-llm 整包集成
- 每条消息自动写记忆、85% 自动压缩（Phase 2）
- 记忆 merge/override 的二次模型仲裁（Phase 1 用相似度 skip）
- 跨 Bot 全局共享记忆
- **本 OpenSpec 阶段不写实现代码**（仅文档与提案）

## Decisions

### 1. 目录结构：分类文件夹 + 索引（推荐方案 C）

**选择**：扩展现有 `souls/{bot-id}/`，新增 `memory/` 子树；`memory.md` 仍在灵魂根目录（与 `load_soul_folder()` 兼容）。

```text
souls/{id}/
  soul.md
  constraints.md
  memory.md              # 层1：极少稳定事实，启动注入；压缩时可自动合并精华
  knowledge/             # 静态知识，全量启动注入，与收藏分离
  memory/
    index.sqlite         # FTS 索引（由 indexer 从下方文件同步）
    items/
      fact/              # 一条一事：{id}.json 或 {id}.md
      preference/
      project/
      relationship/
      quote/
    docs/
      {slug}/            # 一篇收藏一个文件夹
        meta.json        # 标题、来源、标签、摘要、时间
        chunk-001.md
        chunk-002.md
```

**双写规则**：

- 写入记忆 → 先写 `items/` 或 `docs/` 文件 → 再更新 `index.sqlite` 对应行
- 读取给 AI → **只走检索**（index.sqlite FTS），不 `os.walk` 把整个 `memory/` 读进 prompt
- 用户可直接用资源管理器打开 `items/fact/` 查看、手改、删除文件；下次发消息前 `reindex` 或写入时同步索引

**备选**：仅 sqlite 无文件夹 — 不便人工查看，否决。  
**备选**：仅文件夹无索引 — 中文搜索慢，否决。

### 2. 条目文件格式（items）

每条记忆一个文件，便于分类浏览：

```json
{
  "id": "20260604_abc123",
  "type": "preference",
  "content": "用户偏好简短回复",
  "summary": "简短回复",
  "keywords": ["回复风格"],
  "importance": 4,
  "confidence": 0.9,
  "source_session_id": "...",
  "created_at": "2026-06-04T12:00:00",
  "updated_at": "2026-06-04T12:00:00"
}
```

路径：`memory/items/preference/20260604_abc123.json`

`index.sqlite` 表 `memory_items` 存相同字段 + `file_path` + FTS `search_text`。

### 3. 长文收藏（docs）

```text
memory/docs/my-article-slug/
  meta.json
  chunk-001.md
  chunk-002.md
```

chunk 大小 800–1500 字；`index.sqlite` 中 `memory_chunks` 表含 `file_path`、`doc_slug`、`chunk_index`。

### 4. 工具程序：search_memory()

后端固定模块 `retrieval.py`，发消息前调用：

```text
search_memory(soul_folder, query, session_summary?, budget_tokens)
  → 读 index.sqlite FTS
  → 分档 A/B/C 打分
  → 返回 [{type, summary, content_snippet, score}, ...]
```

**不是**让模型自己 `file:read` 扫目录；是 MeClaw 后端在 `build_messages_for_api()` 里自动执行。

### 5. 检索分档与注入

| 档位 | 内容 | 触发 |
|------|------|------|
| A | `memory.md`（已有加载）+ importance≥4 的 items | 检索开 |
| B | FTS `memory_items` top-k | 检索开 |
| C | `memory_chunks` | 意图命中（风格/参考/那篇/喜欢） |

注入：独立 system 段 `## 相关记忆\n...`；`memory_token_budget` 默认 1200。

### 6. 评分公式

```text
score = bm25 * 0.65 + recency * W_type + importance/5 * 0.15
```

quote 几乎不衰减；project 衰减更强。

### 7. 压缩上下文：双管线 + memory.md 自动维护

```text
compress_context()
  ├─ job1: conversation_summary → current_summary（现有）
  └─ job2: memory_extraction（memory_enabled 且非仅检索）
        → JSON 候选 → 过滤 → 去重
        → 写入 memory/items/{type}/{id}.json
        → indexer 更新 index.sqlite
        → importance≥4 且 type∈{fact,preference} 且 confidence≥0.8
           → 合并进 memory.md（一行一条，去重，不超 4KB）
```

**memory.md 维护方式**：

- **自动为主**：压缩时整理器升华精华（用户期望的「顺便来一下」）
- **手动为辅**：用户直接编辑 `memory.md`
- **AI 为辅**：现有 `write_memory_file` / `file:edit` 保留
- **禁止**：长文 chunk、项目流水账、整段聊天贴入 `memory.md`

`memory.md` 合并示例（自动追加，非覆盖全文）：

```markdown
- [2026-06-04] 用户叫小明，偏好简短回复（importance:4）
```

### 8. 记忆整理器（extractor）

后端固定程序；压缩时一次 API 调用输出 JSON 数组。Phase 1 去重：相似度超阈值 → skip。

不写记忆时机：流式中途、切换 Bot、联网结果默认不入库。

### 9. 配置字段

```json
{
  "memory_enabled": true,
  "memory_retrieval_enabled": true,
  "memory_auto_extract": false,
  "memory_token_budget": 1200,
  "memory_extract_threshold_pct": 85
}
```

`bots[]` 可覆盖 `memory_enabled`、`memory_retrieval_enabled`。

### 10. 模块划分（待实现）

```text
backend/memory/
  store.py       # 文件 CRUD：写 items/docs 目录
  indexer.py     # 文件夹 ↔ index.sqlite 同步、FTS search_text（含中文 n-gram）
  retrieval.py   # search_memory()：分档、打分、预算
  extractor.py   # 压缩提取、去重、写文件、合并 memory.md
  intent.py      # 长文意图关键词
```

### 11. UI（待实现）

- 设置 → 记忆：总开关、仅检索、token 预算
- 压缩按钮文案：「压缩上下文（含整理记忆）」
- 「收藏这段话」→ 写 `items/quote/` 或 `docs/`

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 双写不一致（手删文件但索引残留） | 发消息前轻量 `reindex_if_stale()` 或写入时校验 |
| FTS5 中文效果一般 | search_text 含关键词 + 2/3-gram |
| memory.md 自动合并仍膨胀 | 4KB cap + 仅 fact/preference + importance≥4 |
| token 超限 | 硬预算 + 只检索不扫目录 |
| 文件夹条目过多 | 按 Bot 隔离；Phase 2 管理 UI |

## Migration Plan

1. 首次使用：自动创建 `memory/` 子目录与空 `index.sqlite`
2. 现有 `memory.md` 保留，不强制迁入 `items/`
3. 旧 Bot 无 `memory/` 时行为与现版一致，直到用户开启记忆并触发首次写入

## Open Questions

- `memory.md` 超 4KB：Phase 1 警告并跳过自动追加，还是淘汰最旧条目？（建议警告 + 跳过自动追加）
- 手改 `items/*.json` 后是否每次聊天全量 reindex？（建议 mtime 增量 reindex）
