## 0. 文档与提案

- [x] 0.1 更新 `proposal.md`、`design.md`、specs（文件夹 + 双写 + 压缩维护 memory.md）
- [x] 0.2 更新 `docs/记忆系统技术文档.md`、`docs/记忆系统使用帮助.md`
- [x] 0.3 用户确认后开始实现

## 1. 目录与双写骨架

- [x] 1.1 创建 `backend/memory/` 包：`store.py`、`indexer.py`、`retrieval.py`、`extractor.py`、`intent.py`
- [x] 1.2 实现目录初始化：`memory/items/{type}/`、`memory/docs/`、`memory/index.sqlite`
- [x] 1.3 实现 `store.py`：写/删 `items/{type}/{id}.json` 与 `docs/{slug}/chunk-*.md`
- [x] 1.4 实现 `indexer.py`：文件 → sqlite 同步、FTS5、`search_text`（含中文 n-gram）
- [x] 1.5 实现增量 reindex（按文件 mtime 检测手改或外部删除）

## 2. 工具程序检索与注入

- [x] 2.1 实现 `search_memory()`：FTS 检索，非全目录遍历
- [x] 2.2 实现分档 A/B/C 与 bm25 + type 衰减打分
- [x] 2.3 实现 `intent.py` 长文意图关键词
- [x] 2.4 在 `api.py` 的 `build_messages_for_api()` 注入独立 system 记忆块
- [x] 2.5 受 `memory_token_budget` 截断；开关关闭时零影响

## 3. 压缩双管线与 memory.md 自动维护

- [x] 3.1 实现 `extractor.py`：固定 prompt + JSON 候选解析
- [x] 3.2 去重与低质量过滤
- [x] 3.3 扩展 `compress_context()`：job1 摘要 + job2 写 `items/` + reindex
- [x] 3.4 实现 `memory.md` 自动合并（importance≥4 fact/preference，一行一条，4KB cap，去重）
- [x] 3.5 压缩按钮/UI 文案提示「含整理记忆」

## 4. 长文收藏

- [x] 4.1 `collect_document()`：创建 `docs/{slug}/` + chunk 切分 + 索引
- [x] 4.2 `collect_quote()`：写 `items/quote/` + 索引
- [x] 4.3 档位 C 仅意图命中时检索 chunks

## 5. 配置与 API 暴露

- [x] 5.1 `config.example.json` 与 `DEFAULT_CONFIG` 增加记忆全局字段
- [x] 5.2 per-bot 开关覆盖（`memory.config.get_memory_settings` 支持 bot 字段）
- [x] 5.3 `main.py` 暴露：`collect_document`、`collect_quote`、`list_memory_items`、`delete_memory_item`
- [x] 5.4 `memory.md` 超 4KB 时警告并跳过自动追加

## 6. 前端与设置

- [x] 6.1 设置弹窗新增「记忆」分区：总开关、仅检索、token 预算
- [x] 6.2 Bot 编辑 per-bot 自动压缩阈值（记忆 · 自动压缩卡片）
- [x] 6.4 状态面板常驻压缩按钮 + 压缩方向弹窗
- [x] 6.3 消息区「⭐ 收藏/记住」入口

## 7. 验证

- [x] 7.1 模块 smoke test：目录、索引、检索
- [ ] 7.2 手动测试：压缩后 items/ + memory.md（需运行应用）
- [ ] 7.3 手动测试：长文意图门控
- [ ] 7.4 手动测试：手删 json 后 reindex
- [ ] 7.5 手动测试：开关关闭零影响

## 8. Phase 2

- [x] 8.1 自动压缩 + `memory_auto_extract` + 阈值滑块（全局 + per-bot）；发消息前触发
- [x] 8.2 记忆管理浏览 UI（状态面板 · 记忆库，删条目/收藏，打开文件夹）
- [x] 8.2b Bot 编辑 per-bot 记忆读写开关
- [x] 8.2c 自动提取过滤玩笑/低质量 quote（importance&lt;4 不自动记 quote）
- [ ] 8.3 merge/override/conflict 二次模型判断
- [ ] 8.4 embedding_hint 增强中文检索
