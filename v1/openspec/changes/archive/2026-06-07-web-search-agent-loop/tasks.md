# Tasks — web-search-agent-loop

## 1. 结构化检索（backend/web_search.py）

- [x] 1.1 定义 `SearchResult`（query、provider、items、text_for_model、error）与 `search_web_structured()` 入口
- [x] 1.2 Bing local / RSS / DuckDuckGo / SerpAPI 解析路径统一输出 `items[{index,title,url,snippet}]`（每步最多 8 条）
- [x] 1.3 保留 `search_web()` 文本接口或薄包装，确保 tool role 仍只写入 `text_for_model`
- [x] 1.4 补充 `build_citations(steps)`：按 URL 去重聚合引用列表

## 2. 多轮工具循环（backend/api.py）

- [x] 2.1 配置默认值：`web_search_max_rounds=3`、`web_search_max_queries_per_round=3`（api 默认 + config.example.json）
- [x] 2.2 重构 `_call_api`：while 循环非流式 `tools=True`，无 `tool_calls` 或达上限后 break
- [x] 2.3 轮间：推送 assistant `reasoning_content`（复用 `_emit_assistant_message` 或 chunk 推送逻辑）
- [x] 2.4 `_execute_search_tool_calls`：按 per-round cap 截断；返回结构化 step 列表供 UI
- [x] 2.5 达 round 上限仍含 `tool_calls` 时 log 警告并进入最终流式（tools=False）
- [x] 2.6 保持 skipped / error 路径：模型不调 tool、API 失败时的 `_notify_web_status`

## 3. 前端事件与状态（web/js/chat.js）

- [x] 3.1 新增 `onWebSearchStep(payload)`：按 `stepId` append/update 时间线行（searching → done/failed）
- [x] 3.2 精简 `onWebSearchStatus` 为轮次级（analyzing / skipped / error），与步级时间线并存
- [x] 3.3 `onStreamDone` 接收 `webSearchSteps`、`citations`；finalize 时写入消息 data 属性
- [x] 3.4 会话加载/历史渲染：从消息元数据重建 `.web-search-timeline` 与引用按钮

## 4. 联网时间线 UI（web/js/chat.js + web/style.css）

- [x] 4.1 组件 `.web-search-timeline`：竖线 + 多行 `.web-search-step`（🌐 联网检索：query、条数、状态）
- [x] 4.2 替换 ephemeral 单条 status 为主要展示（可保留顶部简要轮次提示）
- [x] 4.3 步级详情 modal/sheet：参数 JSON、结果卡片、折叠「查看原始数据」
- [x] 4.4 引用入口「共 N 条引用」+ 底部/侧滑抽屉（编号、标题、摘要、URL）
- [x] 4.5 暗色主题样式与 `.message-bubble` 布局对齐（快速模式与思考模式均可见）

## 5. 设置与配置 UI

- [x] 5.1 `web/index.html` + `web/js/config.js` + `web/app.js`：暴露 max rounds / max queries per round
- [x] 5.2 设置项附简短说明（非轮询，为工具循环上限）

## 6. 文档与技能

- [x] 6.1 更新 `docs/联网与MCP预留.md`：多轮循环、时间线 UI、配置项
- [x] 6.2 更新 `skills/web-search/instructions.md`：说明可多轮 refine query、检索失败勿编造

## 7. 验收

- [ ] 7.1 手动：开启联网 + 思考，问复杂时效问题（如巡演/新闻），确认时间线多条、轮间有思考、引用抽屉有来源
- [ ] 7.2 手动：`max_rounds=1` 行为与改造前单轮一致且仍显示时间线
- [ ] 7.3 手动：模型跳过 search_web 时显示 skipped，时间线为空
- [ ] 7.4 手动：刷新/重载会话后时间线与引用仍可恢复
