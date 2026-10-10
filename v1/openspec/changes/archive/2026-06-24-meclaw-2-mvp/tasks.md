## 1. 工程脚手架

- [ ] 1.1 创建 `meclaw2/` 目录树（backend、web、data）与 `requirements.txt`
- [ ] 1.2 实现 `MECLAW2_DATA_DIR` 与默认 `meclaw2/data/` 路径解析
- [ ] 1.3 初始化空 `config.json` 模板与 `config.example.json`
- [ ] 1.4 实现首次启动 bootstrap：默认 config、default Bot、default soul
- [ ] 1.5 FastAPI 入口：静态资源挂载 + `GET /health`
- [ ] 1.6 添加 `启动MeClaw2.bat`（uvicorn 127.0.0.1:8766）
- [ ] 1.7 确保默认监听 `127.0.0.1`，不默认开放 CORS `*`

## 2. 存储层

- [ ] 2.1 `config_store`：读写 `config.json`
- [ ] 2.2 `history_store`：`sessions.json` 索引 CRUD
- [ ] 2.3 `history_store`：会话消息文件读写
- [ ] 2.4 `soul_store`：创建 Bot 目录、`soul.md` / `constraints.md` 读写
- [ ] 2.5 新建 Bot 时创建 `memory/.gitkeep` 占位
- [ ] 2.6 JSON 写入统一使用临时文件 + `os.replace` 原子替换
- [ ] 2.7 `config.json` 写入前保留 `.bak` 或提供等价恢复策略

## 3. 供应商与 Provider 适配

- [ ] 3.1 移植/精简 `providers.py`（generic / anthropic / deepseek）
- [ ] 3.2 REST：`GET/PUT /api/config`
- [ ] 3.3 REST：`GET /api/bootstrap`
- [ ] 3.4 REST：供应商 CRUD + `POST /api/providers/{id}/test`（用 profile 自身 model）
- [ ] 3.5 Provider MVP 仅实现文本流式，不实现 tools/reasoning UI
- [ ] 3.6 API Key 在列表、日志、错误中脱敏
- [ ] 3.7 供应商测试与错误信息返回前端

## 4. Bot 域

- [ ] 4.1 REST：Bot CRUD
- [ ] 4.2 REST：`GET/PUT /api/bots/{id}/soul`
- [ ] 4.3 `soul_loader`：组装 system（soul + constraints）
- [ ] 4.4 Bot 绑定 profile 与 model/temperature/max_tokens 覆盖逻辑
- [ ] 4.5 禁止删除仍有关联会话的 Bot，并返回可读错误

## 5. 会话域

- [ ] 5.1 REST：按 `bot_id` 列出会话
- [ ] 5.2 REST：新建 / 切换 / 删除会话
- [ ] 5.3 首条用户消息自动更新会话标题（去换行、截断、空则「新对话」）
- [ ] 5.4 切换会话时返回消息列表 JSON
- [ ] 5.5 消息 schema 增加 `id`、`created_at`、assistant `status`

## 6. 记忆预留（NoOp）

- [ ] 6.1 定义 `MemoryService` Protocol（before_chat / after_turn / on_compress 占位）
- [ ] 6.2 实现 `NoOpMemoryService`
- [ ] 6.3 `ChatService` 注入 memory 并在组装消息时调用 `before_chat`
- [ ] 6.4 生成结束后异步调用 `after_turn`（空实现）

## 7. 聊天与 WebSocket

- [ ] 7.1 `ChatService.build_messages`：soul + history（无记忆块）
- [ ] 7.2 线程池执行流式 LLM，避免阻塞 event loop
- [ ] 7.3 WebSocket `/ws/chat`：send / stop / token / done / stopped / error 事件
- [ ] 7.4 所有生成事件携带 `generation_id`
- [ ] 7.5 MVP 限制单活跃生成，重复 send 返回错误
- [ ] 7.6 停止生成：设置 cancel 标志并中断请求
- [ ] 7.7 完成后持久化 assistant 消息（done/stopped/error 状态一致）

## 8. 前端壳（UI）

- [ ] 8.1 `index.html` 布局：顶栏 + 侧栏 260px + 主聊天区 + composer
- [ ] 8.2 暗色主题 CSS 变量
- [ ] 8.3 `api-client.js`：REST 封装 + WebSocket 连接
- [ ] 8.4 侧栏状态机：`bots` ↔ `sessions` + 返回
- [ ] 8.5 消息渲染与流式光标
- [ ] 8.6 前端启动调用 `/api/bootstrap` 并处理未配置供应商引导
- [ ] 8.7 设置 Modal：供应商 Tab + 机器人 Tab（记忆/群聊灰色占位）
- [ ] 8.8 composer 区消息条数提示
- [ ] 8.9 无可用供应商或 Bot 未绑定供应商时禁用发送并提示

## 9. 闭环验收

- [ ] 9.1 手动验收：配 API → 测试连接通过
- [ ] 9.2 手动验收：创建 2 个 Bot，soul 不同，回复风格可区分
- [ ] 9.3 手动验收：每 Bot 多会话，切换历史正确
- [ ] 9.4 手动验收：重启服务后数据仍在
- [ ] 9.5 手动验收：流式 + 停止生成正常
- [ ] 9.6 手动验收：停止后的 partial assistant reload 后仍显示
- [ ] 9.7 手动验收：API Key 在列表与错误信息中脱敏
- [ ] 9.8 运行 `python -m compileall meclaw2/backend`
- [ ] 9.9 Store 层读写 smoke test（config/session/soul）
- [ ] 9.10 更新 `docs/` 或 `meclaw2/README.md` 快速开始说明
