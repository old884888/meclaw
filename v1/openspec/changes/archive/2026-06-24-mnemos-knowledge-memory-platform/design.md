## Context

- 当前 `meclaw2/` 是一个独立子工程：FastAPI + WebSocket + 原生 Web UI，默认从 `meclaw2/data/` 读写数据。
- 2.0 已经具备或设计了基础聊天闭环：配置、供应商、Bot、Soul、Session、流式聊天。
- 当前记忆层只有 `MemoryService` Protocol 与 `NoOpMemoryService`，适合承接新的分层记忆实现。
- 用户希望 2.0 主线转向 **MNEMOS**：一个清爽、浏览器可打开、本地优先的知识记忆 AI，而不是简单复制 1.0 的所有功能。
- 参考方向：
  - TencentDB Agent Memory：分层记忆、证据可追溯、混合检索、短期 offload。
  - llm-wiki-agent：资料导入、Markdown 知识库、交叉引用、图谱、synthesis。

## Goals / Non-Goals

**Goals:**

- 将 2.0 产品定位、文案和路线图调整为 MNEMOS。
- 保持 `meclaw2/` 当前可运行的本地 Web 架构。
- 设计 iOS 感清爽 UI：留白、卡片、圆角、柔和层次、简洁导航。
- 设计并分阶段落地 TencentDB 式 L0/L1/L2/L3 分层记忆。
- 设计 llm-wiki-agent 风格的 Wiki Mode，作为未来知识整理模式。
- 让 `meclaw2/` 具备后续独立拿出为 MNEMOS 项目的路径。

**Non-Goals:**

- 不在第一阶段直接接入 TencentDB Agent Memory 的 Node Gateway。
- 不在第一阶段引入向量数据库或 embedding 依赖。
- 不在第一阶段实现完整知识图谱可视化。
- 不恢复 1.0 的群聊、编程模式、文件树、技能系统。
- 不做主动联网搜索；仅允许“用户提供 URL 后抓取正文”的导入能力。
- 不默认开放局域网/公网访问。

---

## Roadmap

```text
Phase 0 — MNEMOS Rebrand + Shell
  产品名、标题、默认文案、iOS 感 UI 基线、启动/README 独立化约束
  保持配置、Bot、Soul、Session、流式聊天闭环

Phase 1 — Knowledge Ingest L0/L1
  文本 / Markdown / URL 导入
  L0 原文归档
  L1 知识卡片提取
  SQLite FTS 检索
  问知识库最小闭环

Phase 2 — MemoryService Real Implementation
  before_chat 检索注入
  after_turn 记录对话 L0
  on_compress 提取 L1
  记忆面板与来源追溯

Phase 3 — L2/L3 Layered Memory
  L2 主题/场景聚合
  L3 用户画像/知识画像
  可追溯链路：L3 -> L2 -> L1 -> L0

Phase 4 — Wiki Mode
  Markdown 页面浏览
  [[PageName]] 交叉引用
  分类/标签/实体/概念
  synthesis 综合页
  图谱视图

Phase 5 — Retrieval Upgrade
  embedding 可选
  BM25/FTS + vector + RRF
  短期 offload / Mermaid 任务画布（如需要）
```

---

## Architecture Decisions

### D1. Product Identity: MNEMOS

MNEMOS 是 2.0 主线的产品名。实现阶段应统一：

- 页面标题：`MNEMOS`
- 顶栏 / logo 文案：`MNEMOS`
- 默认 Bot 可命名为 `MNEMOS`
- 默认数据目录仍可短期保留 `meclaw2/data/`，但配置和 README 要说明后续会迁移到 MNEMOS 命名。

短期不强制重命名 Python 包，避免大范围破坏导入路径。推荐顺序：

1. 先改用户可见文案与 README。
2. 再整理启动脚本，使 `meclaw2/` 单独拿出时可运行。
3. 最后再评估包名是否从 `meclaw2.backend` 改为 `mnemos.backend`。

### D2. Web First, Desktop Optional

MNEMOS 默认是本地 Web 应用：

```text
python -m uvicorn meclaw2.backend.main:app --host 127.0.0.1 --port 8766
浏览器打开 http://127.0.0.1:8766
```

桌面壳（pywebview）可后续增加，但不得成为唯一入口。这样能保证：

- 开发调试简单。
- 未来可包装桌面应用。
- 未来可扩展到局域网/平板/移动端，但必须先加访问保护。

### D3. iOS-like UI Direction

视觉关键词：

- 大面积留白或低对比背景。
- 圆角卡片，轻阴影或边框。
- 半透明顶栏/侧栏可选，但不要牺牲可读性。
- 字体层级清晰，按钮少而明确。
- 默认浅色主题优先，暗色主题作为后续补齐。
- 交互尽量“轻”：Modal、Sheet、Popover、Segmented Control。

建议主布局：

```text
┌──────────────────────────────────────────────────────────────┐
│ MNEMOS                                      [Import] [Settings]│
├───────────────┬──────────────────────────────────────────────┤
│ Sidebar       │ Main                                         │
│               │                                              │
│ Chat          │  当前模式内容                                │
│ Knowledge     │  Chat / Knowledge / Memory / Settings        │
│ Memory        │                                              │
│ Wiki (future) │                                              │
└───────────────┴──────────────────────────────────────────────┘
```

第一阶段可以只实现 Chat + Settings 的视觉重构，但 DOM / CSS 命名要为 Knowledge / Memory 留位置。

### D4. Data Root and Independent Extraction

当前默认：

```text
meclaw2/data/
  config.json
  history/
  souls/
```

MNEMOS 后续数据布局建议：

```text
data/
  config.json
  history/
  souls/
  knowledge/
    raw/
      {source-id}.md
    notes/
      {note-id}.md
    sources.json
    index.sqlite
  memory/
    l0/
    l1/
    l2/
    l3/
    index.sqlite
```

短期可以只新增 `knowledge/`，让 `memory/` 继续按 Bot 目录占位。中期再统一成全局 memory 或 bot-scoped memory。

独立拿出 `meclaw2/` 时必须满足：

- 启动脚本不依赖父目录。
- 静态资源路径相对当前工程解析。
- 默认数据目录在当前工程下。
- 可通过环境变量覆盖数据目录。
- README 写明安装依赖与启动命令。

### D5. Knowledge Ingest Pipeline

导入类型：

- 粘贴文本。
- 粘贴 URL。
- 上传/选择 Markdown 文件（本地 Web 初期可先用文本区域或路径输入，文件选择后续完善）。

导入流程：

```text
input
  -> normalize_source()
  -> if URL: fetch readable article text
  -> write L0/raw source
  -> LLM extract note draft
  -> write Markdown note with frontmatter
  -> update SQLite FTS index
```

知识卡片格式：

```markdown
---
id: note_xxx
title: 示例标题
category: 自动分类
tags: [tag1, tag2]
source_id: src_xxx
source_url: https://example.com
created_at: 2026-06-16T20:00:00
layer: L1
---

## 摘要

...

## 要点

- ...

## 相关

[[相关概念]]
```

第一阶段的提取目标：

- title
- summary
- category
- tags
- key_points
- related_terms
- source reference

### D6. Layered Memory Model

MNEMOS 采用 TencentDB 式分层思路，但先实现轻量版本。

| Layer | Name | Content | Storage | First Implementation |
|-------|------|---------|---------|----------------------|
| L0 | Evidence | 原文、网页正文、对话原文、工具结果 | Markdown/JSONL | Phase 1 |
| L1 | Atom | 原子事实、偏好、定义、结论、摘录 | Markdown + frontmatter | Phase 1 |
| L2 | Scenario | 主题块、项目块、场景总结 | Markdown | Phase 3 |
| L3 | Persona/Profile | 用户画像、知识画像、长期策略 | Markdown | Phase 3 |

可追溯性要求：

```text
L3 profile item
  -> references L2 scenario ids
  -> references L1 atom ids
  -> references L0 source ids / line ranges when available
```

任何摘要都不应成为唯一事实来源。用户或 AI 必须能沿引用链回到原文。

### D7. MemoryService Mapping

现有接口：

```python
before_chat(scope, query, session_summary, budget_tokens) -> str
after_turn(scope, session_id, messages) -> None
on_compress(scope, session_id, messages) -> CompressResult
```

后续映射：

- `before_chat`：检索 L1/L2/L3，按 token budget 生成注入块。
- `after_turn`：把完成轮次写入 L0，对轻量事实可排队提取 L1。
- `on_compress`：对长对话生成 session summary，同时提取 L1/L2。

第一版 MemoryService 可以只用 SQLite FTS，不做 embedding：

```text
query -> FTS search L1 notes -> top-k snippets -> system memory block
```

### D8. Wiki Mode

Wiki Mode 不是第一阶段必须实现的完整功能，但设计要预留。

功能边界：

- Knowledge 是“资料库”：导入、卡片、问答。
- Memory 是“AI 对人/任务的记忆”：对话、偏好、画像。
- Wiki Mode 是“整理视图”：把 Knowledge 和 Memory 中稳定内容组织成页面、交叉引用和图谱。

未来目录建议：

```text
data/wiki/
  index.md
  overview.md
  pages/
  entities/
  concepts/
  syntheses/
  graph.json
```

Wiki Mode 输出可以从 `knowledge/notes` 和 `memory/l2/l3` 派生，不一定一开始就作为真源。真源仍是 L0/L1/L2/L3 与 raw。

### D9. Retrieval Strategy

阶段策略：

1. **FTS only**：SQLite FTS，最快、可解释、无额外依赖。
2. **Hybrid optional**：后续增加 embedding 表，做 FTS + vector。
3. **RRF merge**：将关键词和向量结果按 Reciprocal Rank Fusion 合并。
4. **Layer-aware recall**：不同问题优先召回不同层：
   - 事实问题：L1 + L0。
   - 主题理解：L2 + L1。
   - 偏好/风格：L3 + L2。
   - 溯源验证：L0。

### D10. URL Fetch Boundary

“贴 URL 抓正文”属于导入能力，不等同于主动联网搜索。

约束：

- 只抓用户明确提供的 URL。
- 不自动搜索网络。
- 抓取失败要保留 URL 与错误信息。
- 原文必须先存 L0，再做提取。
- 后续可用 `trafilatura`；如果依赖不可用，先用 `requests` + 简单 HTML 清理作为降级。

### D11. Security and Privacy

- 默认只监听 `127.0.0.1`。
- 不默认开启 CORS `*`。
- API Key 继续脱敏展示。
- 知识库和记忆默认本地明文存储，README 必须说明。
- 局域网访问、手机访问、远程访问必须先设计访问 token。
- URL 抓取不应把 API Key、config、history 等本地路径内容暴露给网页。

---

## API Sketch

第一阶段后续可新增：

```text
POST /api/knowledge/import
GET  /api/knowledge/notes
GET  /api/knowledge/notes/{id}
POST /api/knowledge/search
POST /api/knowledge/ask

GET  /api/memory/layers
GET  /api/memory/items?layer=L1
GET  /api/memory/trace/{id}
```

`/api/knowledge/import` 请求示例：

```json
{
  "type": "url",
  "content": "https://example.com/article",
  "mode": "auto"
}
```

`/api/knowledge/ask` 响应应包含答案与来源：

```json
{
  "answer": "...",
  "sources": [
    { "id": "note_xxx", "title": "...", "source_url": "..." }
  ]
}
```

---

## Migration / Compatibility

- 1.0 数据不自动迁移。
- `meclaw2/` 现有数据尽量保留兼容。
- 产品命名变更先影响 UI 文案，不强制迁移目录名。
- 若后续从 `meclaw2/data` 改为 `mnemos/data`，必须提供明确迁移说明或兼容读取。

---

## Risks

| Risk | Mitigation |
|------|------------|
| 一次性做完整分层记忆导致范围过大 | 严格 Phase 化，Phase 1 只做 L0/L1 + FTS |
| UI 重构影响现有聊天闭环 | 先保留当前 API，不改数据 schema，再改视觉 |
| URL 抓取不稳定 | 保留原始 URL 与错误，允许用户粘贴正文兜底 |
| Markdown 卡片格式后续变更 | 使用 frontmatter `schema_version` |
| 2.0 独立化与当前包名冲突 | 分阶段处理，先启动脚本/README，再考虑包名 |
| 记忆与知识边界混淆 | Knowledge 处理资料；Memory 处理对话/偏好/画像；Wiki 是整理视图 |

---

## Open Questions

- 全局知识库还是按 Bot 隔离知识库？建议 Phase 1 先做全局 `knowledge/`，Bot/Soul 只影响回答风格。
- L3 是用户画像、知识画像，还是两者分开？建议分开：`user_profile.md` 与 `knowledge_profile.md`。
- Wiki Mode 的页面是真源还是派生？建议先派生，避免多处真源冲突。
- 是否保留 `meclaw2` 目录名到 MNEMOS 第一个稳定版后再改？建议保留到功能稳定。
