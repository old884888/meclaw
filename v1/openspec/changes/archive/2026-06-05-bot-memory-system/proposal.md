## Why

MeClaw 已有会话历史、`current_summary` 压缩摘要和 `souls/{id}/memory.md` 长期记忆，但三者职责混杂：`memory.md` 易被 AI 无限追加变成 token 黑洞，长文收藏与短期事实无法分库检索，也缺少按 Bot 隔离的可开关记忆管线。需要在不替换现有聊天链路（云端 API、流式、联网 tool）的前提下，建立「稳定事实 + 可检索中期记忆 + 长文收藏」三层结构，**按内容分类存文件夹、由后端工具程序检索后按需注入**，控制 token 消耗。

## What Changes

- 每个 Bot 在 `souls/{id}/memory/` 下按**内容分类分子目录**存放记忆（人类可读），辅以 `memory/index.sqlite` 作 FTS5 搜索索引（**文件夹 + 索引双写**）
- **记忆与长文收藏分离**：`items/{type}/` 存短条目；`docs/{标题}/` 存长文 `meta.json` + `chunk-*.md`
- 发消息前由 `search_memory()` 工具程序检索索引，在独立 system 段注入 top-k，受 `memory_token_budget` 硬限制；**绝不整目录读入 prompt**
- `memory.md` 保留为层 1 稳定事实（~4KB cap）；**压缩上下文时自动合并** importance≥4 的 fact/preference 精华条目（去重合并，非整段粘贴）；仍支持手动编辑与 AI `write_memory_file`
- 压缩上下文双管线：`conversation_summary`（已有）+ `memory_extraction`（写 `items/` + 更新索引 + 可选升华 `memory.md`）
- 配置与 per-bot 开关：`memory_enabled`、`memory_retrieval_enabled`、`memory_auto_extract`、`memory_token_budget`
- 设置 UI：记忆主开关 + 高级选项（仅检索 / 自动整理）
- **本阶段仅更新文档与 OpenSpec，暂不写实现代码**
- Phase 1 实现时不做：向量库、mem-llm、Ollama、85% 自动压缩、复杂 merge 二次模型判断

## Capabilities

### New Capabilities

- `bot-memory`: 每 Bot 独立 `memory/` 目录 + FTS 索引、工具程序检索注入、token 预算、开关、压缩时记忆整理器与 `memory.md` 自动维护
- `memory-doc-collection`: 长文收藏按 `docs/` 目录与 chunk 切片存储、手动「收藏」入口、按意图检索片段注入

### Modified Capabilities

（无既有 openspec 规格需修改。）

## Impact

- **后端（待实现）**：新建 `backend/memory/`（`store.py`、`indexer.py`、`retrieval.py`、`extractor.py`）；`backend/api.py`（`build_messages_for_api` 检索注入）；`backend/main.py`（收藏/记忆 API）；`backend/soul.py`（`memory.md` size cap）
- **前端（待实现）**：设置弹窗记忆分区；composer「收藏这段话」
- **配置（待实现）**：`config.example.json` 记忆字段；`bots[]` per-bot 覆盖
- **数据**：`souls/{bot-id}/memory/` 目录树 + `memory/index.sqlite`
- **文档**：`docs/记忆系统技术文档.md`、`docs/记忆系统使用帮助.md`（已按本方案更新）
- **依赖**：无新增 pip 包（sqlite3 内置、FTS5）
