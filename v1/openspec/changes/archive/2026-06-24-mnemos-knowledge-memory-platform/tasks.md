## 1. MNEMOS 定位与独立化基础

- [x] 1.1 将 2.0 用户可见产品名统一为 `MNEMOS`（页面标题、顶栏、默认文案、空状态）。
- [x] 1.2 保留当前 `meclaw2` 包名与目录名，避免第一步大范围破坏导入路径。
- [x] 1.3 更新 2.0 快速开始说明：安装 `meclaw2/requirements.txt`、启动服务、浏览器访问 `127.0.0.1:8766`。
- [x] 1.4 调整启动脚本或新增独立启动脚本，确保未来 `meclaw2/` 单独拿出时不依赖父目录。
- [x] 1.5 确认静态资源、数据目录、配置读取均通过工程相对路径或环境变量解析。
- [x] 1.6 保持默认监听 `127.0.0.1`，不默认开放公网或 CORS `*`。

## 2. 现有 2.0 闭环回归

- [x] 2.1 验证 `GET /health`、静态首页、WebSocket 聊天入口仍可用。
- [x] 2.2 验证首次启动能创建默认 config、default Bot、default soul。
- [x] 2.3 验证供应商配置、测试连接、Bot 绑定 profile、会话持久化不回退。
- [ ] 2.4 验证流式聊天、停止生成、刷新后历史保留。
- [x] 2.5 保证 API Key 在 UI、日志、错误中脱敏。

## 3. iOS 感 UI Shell

- [x] 3.1 定义 MNEMOS UI 设计变量：背景、卡片、边框、圆角、阴影、字体层级、主色。
- [x] 3.2 将整体视觉从传统暗色聊天壳调整为清爽浅色优先的卡片式布局。
- [x] 3.3 重构顶栏：`MNEMOS` 品牌、当前上下文、Import / Settings 操作入口。
- [x] 3.4 重构侧栏导航，为 `Chat`、`Knowledge`、`Memory`、`Wiki`（future）预留结构。
- [x] 3.5 保持当前 Chat 页面功能完整：消息列表、composer、发送、停止、错误提示。
- [x] 3.6 为未来移动端/窄屏保留 CSS 断点，但本阶段不要求完整移动端体验。

## 4. 数据布局设计落地

- [x] 4.1 新增 `data/knowledge/` 布局初始化。
- [x] 4.2 新增 `data/knowledge/raw/`，保存导入原文。
- [x] 4.3 新增 `data/knowledge/notes/`，保存 L1 知识卡片 Markdown。
- [x] 4.4 新增 `data/knowledge/sources.json` 或等价 source registry，记录 URL、文件、文本来源。
- [x] 4.5 新增 `data/knowledge/index.sqlite`，用于 FTS 检索。
- [x] 4.6 为 Markdown frontmatter 加 `schema_version`，便于后续迁移。

## 5. Knowledge Ingest MVP

- [x] 5.1 后端新增知识导入服务：统一处理 text / markdown / url。
- [x] 5.2 URL 导入只抓用户明确提供的链接，不做主动搜索。
- [x] 5.3 URL 抓取成功后保存正文到 L0/raw；失败时保存 URL 与错误信息。
- [x] 5.4 文本与 Markdown 导入同样先保存 L0/raw。
- [x] 5.5 新增 LLM 提取 prompt：生成 title、summary、category、tags、key_points、related_terms。
- [x] 5.6 将提取结果写为 `knowledge/notes/{id}.md`。
- [x] 5.7 导入后同步更新 SQLite FTS 索引。
- [x] 5.8 前端新增 Import 入口：粘贴文本 / 粘贴 URL / 粘贴 Markdown。
- [x] 5.9 导入完成后显示生成的知识卡片与来源。

## 6. Knowledge Browse / Search / Ask

- [x] 6.1 REST：`GET /api/knowledge/notes`，支持按 category / tag / query 过滤。
- [x] 6.2 REST：`GET /api/knowledge/notes/{id}`，读取 Markdown 卡片。
- [x] 6.3 REST：`POST /api/knowledge/search`，返回 FTS 命中的 notes 与 snippets。
- [x] 6.4 REST：`POST /api/knowledge/ask`，检索 notes 后调用 LLM 综合回答。
- [x] 6.5 `ask` 响应必须包含来源列表（note id、title、source url/source id）。
- [x] 6.6 前端新增 Knowledge 页面：卡片列表、筛选、搜索、卡片详情。
- [x] 6.7 前端新增“问知识库”输入框，回答区显示引用来源。

## 7. MemoryService 基础实现

- [x] 7.1 保留现有 `MemoryService` Protocol，新增真实实现类（例如 `LayeredMemoryService`）。
- [x] 7.2 `before_chat` 使用 FTS 检索 L1 notes，按 `memory_token_budget` 生成注入块。
- [x] 7.3 注入块必须包含简短标题、摘要、来源 id，避免塞入整篇原文。
- [x] 7.4 `after_turn` 将对话轮次保存为 L0 conversation evidence。
- [x] 7.5 `on_compress` 先保留接口，可在后续阶段提取 L1 atoms。
- [x] 7.6 配置项控制：`memory_enabled`、`memory_retrieval_enabled`、`memory_write_enabled`。
- [x] 7.7 UI 设置中显示记忆开关与 token budget。

## 8. L0/L1 分层记忆

- [x] 8.1 定义 L0 source/evidence schema。
- [x] 8.2 定义 L1 atom/note schema。
- [x] 8.3 L1 必须引用 L0 source id。
- [x] 8.4 实现 trace API：从 L1 note 查看对应 L0 原文。
- [x] 8.5 Memory 页面展示 L0/L1 分层列表。
- [x] 8.6 编写 smoke test：导入资料 -> 生成 L1 -> 检索 -> trace 到 L0。

## 9. L2/L3 分层记忆

- [x] 9.1 预留 `data/memory/l2/` 与 `data/memory/l3/` 目录初始化。
- [x] 9.2 L2 按 category 自动聚合 L1，API + Memory UI。
- [x] 9.3 L3 从 L2 生成 `knowledge_profile`，API + Memory UI。
- [x] 9.4 导入后自动 L2 聚合；`before_chat` 支持 L2 主题块检索注入。
- [x] 9.5 L3 -> L2 -> L1 -> L0 可追溯（Memory 分层列表 + trace API）。
- [x] 9.6 一键聚合 L2+L3 按钮（`/api/memory/aggregate-all`）。

## 10. Wiki Mode

- [x] 10.1 Wiki 导航已启用。
- [x] 10.2 导入后自动 rebuild wiki；`data/wiki/` 目录与 graph.json。
- [x] 10.3 知识卡片 `[[交叉引用]]` 写入 notes。
- [x] 10.4 从 notes 派生 wiki pages。
- [x] 10.5 graph.json 节点/边 UI 展示（简版可视化）。
- [x] 10.6 完整交互式图谱（Phase 5+，可选）。

## 12. Wiki 页面浏览与数据备份

- [x] 12.1 Wiki 页面详情 API：`GET /api/wiki/pages/{id}`，含 markdown、出链/入链。
- [x] 12.2 概念页 stub 自动生成（`[[交叉引用]]` 目标页）。
- [x] 12.3 前端 Wiki 页面 Markdown 渲染与 `[[链接]]` 跳转。
- [x] 12.4 Knowledge 详情「在 Wiki 中打开」跳转。
- [x] 12.5 数据备份：`GET /api/system/export` + 设置页「数据」Tab。

## 10.5 Retrieval Upgrade（基础版）

- [x] 10.5.1 新增 hybrid 检索：FTS + 本地语义向量 + RRF 融合。
- [x] 10.5.2 `KnowledgeService.search/ask/list_notes` 支持 `strategy` 参数（`hybrid` / `fts`）。
- [x] 10.5.3 配置新增 `knowledge_retrieval_strategy`、`memory_retrieval_strategy`。
- [x] 10.5.4 设置页可切换检索策略，问答结果显示实际策略。
- [x] 10.5.5 `before_chat` 支持按配置选择 memory 注入检索策略。
- [x] 10.5.6 新增 `test_hybrid_smoke.py` 回归测试。

## 11. 测试与验收

- [x] 11.1 运行 `python -m compileall meclaw2/backend`。
- [x] 11.1b 自动化 smoke：`test_knowledge_smoke.py`、`test_l2_l3_smoke.py`、`test_api_smoke.py`。
- [x] 11.1c 验收指南：`meclaw2/docs/验收指南.md`。
- [ ] 11.2 手动验收：浏览器打开 MNEMOS 首页。
- [ ] 11.3 手动验收：配置 API、测试连接、发送一条聊天消息。
- [ ] 11.4 手动验收：导入一段文本，生成知识卡片。
- [ ] 11.5 手动验收：导入一个 URL，保存 raw 并生成知识卡片。
- [ ] 11.6 手动验收：搜索知识卡片，结果包含 snippets。
- [ ] 11.7 手动验收：问知识库，回答带来源。
- [ ] 11.8 手动验收：开启 memory retrieval 后，聊天能引用已导入知识。
- [ ] 11.9 手动验收：重启服务后 config、history、knowledge、memory 数据仍在。
- [x] 11.10 更新 README 或 docs，说明 MNEMOS 当前阶段、启动方式、数据存储位置与隐私边界。
