## 0. 文档与确认

- [x] 0.1 创建 OpenSpec 变更文档（proposal、design、spec、tasks）
- [x] 0.2 用户确认方案后开始实现

## 1. Entry 存储层（store.py）

- [x] 1.1 在 `store.py` 中新增 `entries_dir(soul_folder)` 函数，返回 `memory/entries/` 路径
- [x] 1.2 新增 `ensure_layout()` 中创建 `entries/` 目录
- [x] 1.3 新增 `write_entry(soul_folder, entry_data)` 函数：接受 title/type/importance/keywords/related/summary/points，生成 YAML frontmatter + Markdown body，写入 `entries/{date}-{slug}.md`
- [x] 1.4 新增 `read_entry(file_path)` 函数：读取 entry 文件，解析 YAML frontmatter（含 related）和 Markdown body，返回结构化数据
- [x] 1.5 新增 `list_entries(soul_folder, limit)` 函数：列出所有 entry 文件，返回排序后的元数据列表
- [x] 1.6 新增 `delete_entry(soul_folder, slug)` 函数：删除 entry 文件
- [x] 1.7 修改 `ensure_layout()` 确保 `entries/` 目录在初始化时创建

## 2. FTS5 索引层（indexer.py）

- [x] 2.1 在 `_init_schema()` 中新增 `memory_entries_index` 表（entry_id, file_path, entry_type, importance, created_at, file_mtime, search_text, summary, keywords）
- [x] 2.2 在 `_init_schema()` 中新增 `memory_entries_fts` 虚拟表（entry_id UNINDEXED, entry_type UNINDEXED, importance UNINDEXED, created_at UNINDEXED, search_text）
- [x] 2.3 新增 `index_entry_file(conn, file_path)` 函数：读取 entry 文件，构建 search_text（keywords + 摘要 + 要点 + 中文 n-gram），插入索引表和 FTS 表
- [x] 2.4 修改 `reindex_all()` 遍历 `entries/` 目录并索引
- [x] 2.5 修改 `reindex_if_stale()` 检测 entry 文件变更并增量索引
- [x] 2.6 新增 `index_after_entry_write(soul_folder, entry_path)` 函数

## 3. Extraction Prompt 重写（extractor.py）

- [x] 3.1 重写 `EXTRACTION_PROMPT`：要求 LLM 输出单篇 Markdown 文档（YAML frontmatter 含 related + 摘要 + 要点 + 关键词），不再输出 JSON 数组
- [x] 3.2 重写 `EXTRACTION_PROMPT_MAX_QUOTES`：在标准 prompt 基础上额外请求最多 3 条 quote
- [x] 3.3 新增 `parse_entry_response(text)` 函数：解析 LLM 返回的 Markdown，提取 YAML frontmatter 和 body 各 section
- [x] 3.4 修改 `extract_candidates()` 返回格式从 JSON 数组改为单篇 entry 结构
- [x] 3.5 修改 `apply_candidates()` 调用 `write_entry()` 写入 `entries/`，替代多次 `write_item()` 写入 `items/`
- [x] 3.6 修改 `apply_candidates()` 中 memory.md 更新逻辑：追加索引条目（日期 + 标题 + 一句话描述）替代追加事实行
- [x] 3.7 保留旧 `parse_extraction_response()` 和 `is_low_quality()` 函数作为 legacy 兼容

## 4. 检索层适配（retrieval.py）

- [x] 4.1 修改 `search_memory()` 新增对 `memory_entries_fts` 的查询
- [x] 4.2 合并 entries 和 items 的检索结果，entries 优先排序
- [x] 4.3 新增 related entry 加载逻辑：FTS 命中 entry 后，读取其 related 字段，尝试加载关联 entry 作为补充上下文（在剩余 token 预算内）
- [x] 4.4 调整 token 预算分配：优先分配给完整 entry（每篇 300-500 token），剩余预算给 related entries 和 legacy items
- [x] 4.5 修改 `format_memory_block()` 适配 entry 格式输出：展示日期、标题、摘要、要点
- [x] 4.6 保留 legacy items 的格式化输出作为降级

## 5. memory.md 索引逻辑

- [x] 5.1 修改 `append_memory_md_line()` 或新增 `append_entry_index()` 函数：追加 `- {date} [{title}]({path}) — {description}` 格式的索引行
- [x] 5.2 修改 `apply_candidates()` 中的 memory.md 更新调用，改用新的索引追加函数
- [x] 5.3 保持 memory.md 的 4KB cap 和去重逻辑

## 6. 常量更新（constants.py）

- [x] 6.1 新增 `ENTRY_TYPES` 常量（复用 ITEM_TYPES + 可能的扩展）
- [x] 6.2 新增 entry 相关的 recency half-life 和 weight 配置

## 7. 前端适配（memory.js）

- [x] 7.1 修改记忆面板渲染逻辑，支持展示 entries 列表（日期、标题、摘要）
- [x] 7.2 点击 entry 展开显示要点和关键词
- [x] 7.3 保留 legacy items 的展示区域
- [x] 7.4 删除 entry 功能适配新格式

## 8. 验证

- [x] 8.1 手动测试：压缩后 entries/ 目录生成正确的 Markdown 文件
- [x] 8.2 手动测试：FTS5 索引正确收录 entry 内容
- [x] 8.3 手动测试：检索返回完整 entry 而非碎片
- [x] 8.4 手动测试：memory.md 索引格式正确
- [x] 8.5 手动测试：旧 items 检索仍然正常
- [x] 8.6 手动测试：前端记忆面板正确展示 entries 和 items
