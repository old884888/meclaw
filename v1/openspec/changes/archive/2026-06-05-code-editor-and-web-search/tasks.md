## 1. 编辑器设置与配置

- [x] 1.1 `config.example.json` / 迁移逻辑增加 `editor_word_wrap`（默认 true）
- [x] 1.2 设置弹窗新增「编辑器」卡片：自动换行开关，保存时写入 `save_config`
- [x] 1.3 加载配置时把 `editor_word_wrap` 应用到代码模式编辑器 CSS 类

## 2. 可编辑预览 UI

- [x] 2.1 调整 `web/index.html` 预览区：可编辑区、保存按钮、脏/已保存状态图标
- [x] 2.2 新建或重构 `web/js/code-editor.js`（或扩展 `preview.js`）：buffer、dirty 检测、换行样式
- [x] 2.3 `web/style.css`：编辑器、工具栏、换行/nowrap、状态图标样式
- [x] 2.4 保留复制、发送给 AI；发送时使用当前 buffer 内容

## 3. 后端写盘与安全

- [x] 3.1 `file_ops.py` 实现 `save_working_file(working_dir, rel_path, content)`（路径前缀校验）
- [x] 3.2 `main.py` 暴露 `save_working_file` 给 pywebview
- [x] 3.3 前端 Save / Ctrl+S 调用 API 并更新已保存状态；失败 toast/错误行

## 4. 快捷键与新建文件

- [x] 4.1 全局/预览区监听 Ctrl+S → 保存当前文件
- [x] 4.2 Ctrl+N：提示相对路径，在 `working_dir` 创建空文件并打开编辑（无自动补全）
- [x] 4.3 AI `file:edit` 或外部变更时：脏 buffer 提示是否重载

## 5. 联网 Function Calling（Phase A）

- [x] 5.1 `backend/web_search.py`（或 `search.py`）：`search_web(query)` 抽象 + 默认 provider 实现
- [x] 5.2 `config` 字段：`web_search_provider`、`web_search_api_key`（可选）；设置 UI 文案说明
- [x] 5.3 `api.py`：启用时注入 `search_web` function schema；实现 tool-call 循环（上限 3 轮）
- [x] 5.4 `skills.py` / `wants_web_search`：启用技能或 bot 标志时打开 function tools（禁止 `web_search` type）
- [x] 5.5 更新 `skills/web-search` 的 `skill.json` 与 `instructions.md`
- [x] 5.6 日志/状态：检索时写入 API 日志；失败时友好 `onError`

## 6. 文档与验证

- [x] 6.1 `docs/API参考.md` 补充 `save_working_file`、编辑器配置、`search_web` 循环
- [ ] 6.2 手动验证：编辑保存、越界路径拒绝、换行开关、勾选联网后问时效性问题
- [ ] 6.3 手动验证：未配置 Key 时默认 provider；400 不再出现 `web_search` variant 错误

## 7. 后续预留（本变更不实现，仅注释/文档）

- [x] 7.1 在 `design.md` 或 `docs/` 记录 MCP Phase B 接口草图（可选任务，实现时勾选）
