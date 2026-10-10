# MeClaw API / 前端参考

> 查接口、DOM、config 全字段请看本文件。目录与路径约定见 [系统结构.md](./系统结构.md)。

## 后端模块

### backend/api.py — MeClawAPI 基类

**配置管理：**
| 方法 | 作用 |
|------|------|
| `load_config()` | 加载配置，旧格式自动迁移到 bot 结构 |
| `save_config(json)` | 保存配置 |
| `get_config()` | 返回当前配置 |

**Bot 管理：**
| 方法 | 作用 |
|------|------|
| `get_bots()` | 返回机器人列表 + 当前激活 ID |
| `get_active_bot()` | 返回当前激活的机器人配置（浅拷贝） |
| `switch_bot(id)` | 切换机器人（重置会话上下文） |

**Profile 管理：**
| 方法 | 作用 |
|------|------|
| `get_active_profile()` | 返回当前 bot 关联的 API 配置（bot 参数覆盖优先） |
| `switch_profile(id)` | 切换当前 bot 的 API 配置 |
| `test_connection()` | 测试 API 连通性 |

**对话：**
| 方法 | 作用 |
|------|------|
| `send_message(json)` | 发送消息，组装上下文后调用 API |
| `build_messages_for_api(msgs)` | 组装 system + 摘要 +（code 模式）read_files + **全部**非 system 对话（含多模态 + reasoning_content 回传） |
| `build_system_prompt()` | 组装完整 system prompt（从当前 bot 的 soul_folder 加载） |
| `_has_file_ops(content)` | 判断消息是否包含 file: 操作标记（用于 reasoning_content 回传决策） |
| `_build_deepseek_payload(msgs, bot, profile, max_tokens)` | 构建 DeepSeek 专属 payload（深度思考 + 联网搜索） |
| `_call_api(messages)` | SSE 流式请求 |
| `_call_api_sync(messages)` | 非流式请求（用于压缩） |
| `stop_generation()` | 停止生成 |

**上下文：**
| 方法 | 作用 |
|------|------|
| `calc_context_usage()` | 计算上下文使用情况，返回 JSON |
| `estimate_tokens(text)` | 估算 token 数（字符数 / 2） |

### backend/session_files.py — 对话文件目录

| 函数 | 作用 |
|------|------|
| `get_receive_root(config, app_dir)` | 对话文件根（`receive_dir` 或 `downloads/`） |
| `get_session_dir(root, session_id)` | `{根}/{对话ID}/` |
| `get_session_files_dir(root, session_id)` | `{根}/{对话ID}/files/` |
| `remove_session_storage(root, session_id)` | 删会话时删除对应对话目录 |
| `layout_pattern(root)` | 路径模式说明字符串 |

### backend/file_ops.py — 文件操作模块

| 函数 | 作用 |
|------|------|
| `select_folder(window)` | 系统文件夹选择 |
| `get_file_tree(path)` | 递归扫描目录 |
| `read_file(path)` | 读取文件（截断 50KB/1000行） |
| `parse_file_operations(response)` | 解析 file:create/edit/delete/mkdir 标记 |
| `execute_file_operation(json, workdir)` | 执行操作（路径安全 + 自动备份） |
| `save_working_file(workdir, rel_path, content)` | 用户编辑器保存（路径前缀校验，覆盖前备份） |
| `resolve_working_abs_path(workdir, rel_path)` | 解析工作区内绝对路径，越界返回 None |
| `get_backup_list(workdir)` | 备份列表 |
| `restore_backup(backup, original, workdir)` | 恢复备份 |
| `generate_diff(old, new)` | 生成 diff |
| `is_image_file(path)` | 判断是否为图片文件 |
| `is_text_file(path)` | 判断是否为文本文件 |
| `get_file_info(path)` | 返回文件元信息（名称、大小、类型） |
| `read_image_as_base64(path)` | 图片转 base64 data URL |
| `parse_file_sends(response)` | 解析 AI 回复中的 `<!--file:send:path=...-->` 标记 |
| `copy_to_receive_dir(path, receive_dir, workdir)` | 复制文件到接收目录（路径安全 + 同名重命名） |

### backend/web_search.py — 联网检索

| 函数 | 作用 |
|------|------|
| `search_web(query, provider, api_key)` | 执行检索，返回文本摘要供 tool 消息使用 |
| `SEARCH_WEB_TOOL` | OpenAI 格式 `search_web` function 定义 |

启用逻辑：`skills.wants_web_search(bot, global_enabled)` 为真时，`api.py` 在请求中加入 tools 并处理最多 3 轮 tool call。

### backend/history.py — 对话历史

| 函数 | 作用 |
|------|------|
| `load_sessions()` | 加载会话列表 |
| `create_session(...)` | 创建新会话（支持 `bot_id` 或 `group_id` + `member_bot_ids`、`mode`、`working_dir`） |
| `save_session(data)` | 保存会话 |
| `delete_session(id)` | 删除会话 |
| `delete_sessions(ids)` | 批量删除会话 |
| `rename_session(id, title)` | 重命名 |
| `load_session_messages(id)` | 加载会话消息 |
| `append_messages(id, msgs)` | 追加消息（自动生成标题） |
| `save_summary(id, summary)` | 保存压缩摘要 |
| `export_session_markdown(id)` | 导出 Markdown |
| `search_sessions(keyword)` | 搜索所有会话的标题和消息内容，返回匹配片段 |
| `update_session_fields(id, **fields)` | 更新会话的指定字段（同时更新索引和会话文件） |

### backend/soul.py — 灵魂文件夹

| 函数 | 作用 |
|------|------|
| `load_soul_folder(path)` | 加载所有 .md 文件，按优先级拼接 |

### backend/skills.py — 技能系统

| 函数 | 作用 |
|------|------|
| `scan_skills(app_dir)` | 扫描 skills/ 目录，返回技能列表 |
| `get_enabled_skills(bot_config, app_dir)` | 获取 Bot 已启用的技能详情 |
| `load_skill_instructions(skill_path)` | 读取 instructions.md |
| `create_default_skill(app_dir)` | 创建内置示例技能（仅首次运行） |

### backend/code_mode.py — 编程模式

| 函数/类 | 作用 |
|---------|------|
| `generate_project_overview(folder_path)` | 生成项目索引概览（≤1000 token） |
| `quick_summary(filepath, ext, head_content)` | 基于结构特征生成一句话摘要 |
| `safe_read_file(filepath)` | 安全读取文件，自动检测编码 |
| `ReadFilesManager` | 管理编程模式下读取的文件上下文（内存中，不持久化） |
| `ReadFilesManager.add_file(path, content)` | 添加或更新文件（语义去重） |
| `ReadFilesManager.get_context_messages()` | 返回文件上下文（单条 system 消息） |
| `ReadFilesManager.save_snapshot(msg_id)` | 保存快照 |
| `ReadFilesManager.restore_snapshot(msg_id)` | 恢复快照 |
| `ReadFilesManager.get_info()` | 返回文件列表和使用量 |
| `ReadFilesManager.clear()` | 清空所有文件和快照 |

### backend/main.py — MeClawAPIWithFiles 扩展类

继承 MeClawAPI，新增：

**Bot 管理：**
| 方法 | 作用 |
|------|------|
| `save_bot(json)` | 保存 Bot；新建时创建 `souls/{id}/`；`soul_folder` 存相对路径 |
| `to_config_relative_path(path)` | （api.py）应用根内路径转相对路径 |
| `delete_bot(id)` | 删除机器人（至少保留一个） |
| `select_soul_folder()` | 弹出系统文件夹选择对话框 |
| `preview_soul_folder(path)` | 预览灵魂文件夹内容 |
| `get_soul_folder()` | 返回当前 bot 的灵魂文件夹路径 |
| `write_memory_file(content)` | 写入当前 bot 的 memory.md |

**文件操作：**
| 方法 | 作用 |
|------|------|
| `select_folder()` | 选择工作文件夹 |
| `get_file_tree()` | 扫描工作目录 |
| `read_file(path)` | 读取文件（相对路径自动拼接） |
| `save_working_file(rel_path, content)` | 保存工作区内文件；成功时前端 `onWorkingFileSaved` |
| `parse_file_operations(response)` | 解析操作标记 |
| `execute_file_operation(json)` | 执行操作 + 刷新文件树 |
| `get_diff(path, content)` | 获取 diff |
| `get_backup_list()` | 备份列表 |
| `restore_backup(backup, original)` | 恢复备份 + 刷新文件树 |
| `select_attachments()` | 弹出文件选择对话框，返回文件信息+base64/文本内容 |
| `get_receive_dir()` | 返回对话文件**根**目录 |
| `get_receive_layout()` | 返回根路径与 `{ID}/files/` 模式说明 |
| `select_receive_dir()` | 设置 `receive_dir` 根目录 |
| `open_receive_dir()` | 打开文件根目录 |
| `open_session_files_dir(session_id?)` | 打开当前/指定对话的 `files/` 子目录 |
| `process_file_sends(content)` | 复制到 `{根}/{当前对话ID}/files/` |

**技能系统：**
| 方法 | 作用 |
|------|------|
| `get_skills()` | 返回所有可用技能列表 |
| `open_skills_dir()` | 用系统文件管理器打开技能目录 |

**对话历史：**
| 方法 | 作用 |
|------|------|
| `get_sessions()` | 会话列表 |
| `new_session()` | 创建新会话（关联当前 bot_id） |
| `switch_session(id)` | 切换会话（自动切换 bot，返回 mode 和 working_dir） |
| `switch_mode(mode)` | 切换模式（chat/code），更新当前会话 |
| `set_working_dir(path)` | 设置编程模式的工作目录，更新当前会话 |
| `delete_session(id)` | 删除会话 |
| `delete_sessions(ids_json)` | 批量删除会话 |
| `rename_session(id, title)` | 重命名会话 |
| `save_current_messages(user, assistant)` | 保存消息到历史 |
| `compress_context(direction)` | 压缩上下文（支持方向输入） |
| `export_session(id)` | 导出会话 |
| `search_sessions(keyword)` | 搜索所有会话内容 |
| `rollback_to_message(msg_index)` | 回退到指定消息（保存被移除消息到 _rollback/） |
| `new_task()` | 新建任务（继承工作目录和 Bot，清空对话和 read_files） |
| `handle_file_read(path, lines_range)` | 处理 file:read 标记，读取文件并注入 read_files |
| `get_read_files_info()` | 返回 read_files 状态 JSON |

**上下文：**
| 方法 | 作用 |
|------|------|
| `get_context_usage()` | 返回上下文使用情况（供前端调用） |

**群聊：**
| 方法 | 作用 |
|------|------|
| `get_groups()` | 群聊列表 |
| `create_group(name, member_bot_ids_json, avatar)` | 创建群聊 |
| `get_group_meta(group_id)` / `update_group(...)` / `delete_group(group_id)` | 群元数据 CRUD |
| `get_group_sessions(group_id)` | 某群的会话列表 |
| `new_group_session(group_id)` | 新建群会话 |
| `postprocess_group_assistant(speaker_bot_id, content, chain_state_json)` | 群回复后 @ 补全与接话链 |
| `council_arbitration(action, option_index)` | 专家会议仲裁：`select` / `deepen` / `end` |
| `open_group_folder(group_id)` | 打开群记忆目录 |

**记忆：**
| 方法 | 作用 |
|------|------|
| `get_memory_settings()` | 当前 Bot 有效记忆配置（继承全局） |
| `list_memory_entries(limit)` / `delete_memory_entry(slug)` | entries 浏览/删除 |
| `list_memory_items(limit)` / `delete_memory_item(id, type)` | items 浏览/删除 |
| `list_memory_docs(limit)` / `delete_memory_document(slug)` | docs 浏览/删除 |
| `collect_quote(text)` / `collect_document(title, content, tags_json)` | 收藏好句/长文 |
| `open_memory_folder()` | 打开当前记忆目录 |

---

## 前端模块

### web/index.html — 页面结构

| 区域 | 元素 ID | 说明 |
|------|---------|------|
| 配置弹窗 | `#config-modal` | API 配置列表 + 全局设置 |
| API 编辑弹窗 | `#profile-edit-modal` | 单个 API 配置编辑（别名/URL/Key/模型） |
| 侧边栏 | `#sidebar` | 下拉切换（对话/文件/状态），默认开启 |
| 侧边栏下拉 | `#sidebar-dropdown-btn` | 侧边栏面板选择下拉菜单 |
| 侧边栏切换 | `#btn-toggle-sidebar` | header ☰ 按钮，切换侧边栏显隐 |
| 对话面板 | `#chat-panel` | 会话列表 + 新建 |
| 文件面板 | `#files-panel` | 文件树 + 回退按钮 |
| 状态面板 | `#status-panel` | 上下文概览、容量视图、占用明细 |
| 预览面板 | `#file-preview` | 文件内容预览 |
| 聊天区域 | `#chat-area` | 消息列表 + 输入框（含 📎 附件按钮） |
| 确认弹窗 | `#confirm-modal` | 文件操作确认 |
| 回退弹窗 | `#rollback-modal` | 备份回退 |
| 压缩弹窗 | `#compress-modal` | 压缩确认 |
| Toast | `#compress-toast` / `#global-toast` | 压缩进度提示 / 通用 toast（复制成功等） |
| Bot 选择器 | `#bot-selector` | header 机器人头像+名称，点击弹出下拉 |
| Bot 下拉 | `#bot-dropdown` | 机器人切换下拉菜单 |
| Bot 管理弹窗 | `#bot-manager-modal` | 机器人列表管理 |
| Bot 编辑弹窗 | `#bot-edit-modal` | 机器人编辑表单 |
| Emoji 选择器 | `#emoji-picker-modal` | 头像 emoji 选择 |

### web/app.js — 主入口

全局状态声明、DOM 引用、事件绑定、pywebviewready 初始化。包含侧边栏下拉菜单切换逻辑（`switchSidebarTab`）和模式切换（`switchMode`、`setCodeWorkDir`）。

### web/js/utils.js — 工具函数

| 函数 | 作用 |
|------|------|
| `escapeHtml(str)` | HTML 转义 |
| `formatTime(isoStr)` | 时间格式化（今天只显示时分，否则显示月日时分） |
| `getFileIcon(filename)` | 根据扩展名返回 emoji 图标 |

### web/js/config.js — 配置管理

| 函数 | 作用 |
|------|------|
| `getActiveBot(config)` | 从配置中获取当前激活的机器人 |
| `getActiveProfile(config)` | 从配置中获取当前激活的 API |
| `refreshConfig()` | 重新加载配置 |
| `updateModelDisplay()` | 更新侧边栏模型名显示 |
| `showConfigModal()` / `hideConfigModal()` | 配置面板 |
| `renderProfilesList()` | API 配置列表（整行可点击选中） |
| `showProfileEditModal()` / `hideProfileEditModal()` | API 编辑弹窗（仅别名/URL/Key/模型） |
| `showTestResult()` | 测试连接结果 |

### web/js/chat.js — 对话核心

| 函数 | 作用 |
|------|------|
| `sendMessage()` | 发送消息（含上下文满守卫 + 队列逻辑） |
| `sendImmediately(text)` | 立即发送消息（不经过队列） |
| `processQueue()` | 处理消息队列（生成完成后自动消费） |
| `removeFromQueue(index)` | 从队列移除指定消息 |
| `renderQueue()` | 渲染消息队列 UI |
| `stopGeneration()` | 停止生成 |
| `setGenerating(state)` | 切换生成状态 UI（显示/隐藏发送/停止按钮） |
| `getFontSizes()` | 获取字体大小配置 |
| `renderMarkdown(text)` | 渲染 Markdown（`marked.parse`，无 DOMPurify） |
| `copyMessageText(text)` | 复制文本到剪贴板（成功/失败显示 toast） |
| `showToast(msg, duration)` | 全局 toast 提示（自动创建 #global-toast 元素） |
| `regenerateLastResponse()` | 重新生成最后一条 AI 回复（保留旧版本，支持版本导航） |
| `switchVersion(row, index)` | 切换消息版本（更新内容/思考块/操作按钮） |
| `updateVersionNav(row)` | 创建 ◀ 1/3 ▶ 版本导航，非最新版本时隐藏重新回答按钮 |
| `addMessage(role, content, isStreaming, animate, attachments)` | 添加消息气泡（animate 控制入场动画，attachments 显示附件） |
| `scrollToBottom()` | 滚动到底部 |
| `conditionalScrollToBottom()` | 条件滚动（仅在用户接近底部时） |
| `checkNearBottom()` | 检查用户是否在底部附近 |
| `showScrollToBottomBtn()` / `hideScrollToBottomBtn()` | 显示/隐藏「回到底部」按钮 |
| `autoResize()` | 输入框自动调高 |
| `createThinkingBlock()` | 创建流式思考块（展开状态） |
| `toggleThinking(block)` | 切换思考块展开/折叠（动态创建/移除 thinking-content 元素） |
| `collapseThinking()` | 折叠当前思考块 |
| `onReasoningToken(token)` | Python 回调：接收推理 token |
| `onToken(token)` | Python 回调：接收内容 token |
| `onStreamDone(resultJson)` | Python 回调：流式完成（接收 `{reasoning, content}`） |
| `onCouncilStart(payload)` | 专家会议开始 |
| `onCouncilRound(payload)` | 轮次状态（`roundId` / `label` / `status`） |
| `onCouncilSpeaker(payload)` | 发言者状态（含 `role` / `confidence` / `basis`） |
| `onCouncilToken(payload)` | 会议流式 token |
| `onCouncilBlackboard(data)` | 共享黑板快照 |
| `onCouncilArbitration(payload)` | 人类仲裁停靠（展示方案与推荐） |
| `onCouncilDone(payload)` | 会议结束或中断 |
| `toggleCouncilMode()` | 切换群 composer「专家会议」开关 |
| `onError(errorMsg)` | Python 回调：错误处理 |
| `renderAIFiles(bubble, files, insertAfter)` | 渲染 AI 发送的文件（图片预览 + 文件卡片） |
| `renderAIFilesFromHistory(bubble, files, insertAfter)` | 渲染历史中的 AI 文件（文件信息卡片，图片已过期） |
| `renderMessage(msg, animate)` | 渲染单条消息（animate 控制入场动画，编程模式渲染 file: 记录块） |
| `rollbackToMessage(row)` | 回退到指定消息（确认 + 保存 _rollback/ + 重渲染） |

### web/js/bot.js — 机器人管理 + 上下文进度条

**全局变量：**
| 变量 | 作用 |
|------|------|
| `EMOJI_NORMAL_BOT` / `EMOJI_ABSTRACT_BOT` / `EMOJI_USER` | Emoji 数据 |
| `emojiPickerTarget` / `emojiPickerCallback` | Emoji 选择器状态 |
| `localTokenCount` | 本地累加 token 估算值 |
| `isContextFull` | 上下文是否已满（满时禁用发送） |

| 函数 | 作用 |
|------|------|
| `loadBots()` | 加载机器人列表 |
| `renderBotDropdown(bots, activeBotId)` | 渲染机器人下拉菜单 |
| `switchBot(botId)` | 切换机器人（清空对话、刷新 UI、刷新上下文） |
| `updateBotDisplay()` | 更新 header 机器人头像和名称 |
| `showBotDropdown()` / `hideBotDropdown()` | 机器人下拉显隐 |
| `showBotManager()` / `hideBotManager()` | 机器人管理弹窗 |
| `renderBotList(bots, activeBotId)` | 渲染机器人列表（含编辑/删除按钮） |
| `showBotEditModal(bot)` / `hideBotEditModal()` | 机器人编辑弹窗 |
| `saveBot()` | 保存机器人 |
| `browseSoulFolder()` | 浏览灵魂文件夹 |
| `previewSoulFolder(path)` | 预览灵魂文件夹内容 |
| `showEmojiPicker(target, callback)` / `hideEmojiPicker()` | Emoji 选择器 |
| `renderEmojiPicker(target)` | 渲染 emoji 网格（user 只显示正常类别，bot 显示正常+抽象） |
| `selectEmoji(emoji)` | 选择 emoji |
| `updateContextState(percentage)` | 上下文满时禁用发送按钮 |
| `updateContextBarIncremental(delta)` | 本地增量更新 |
| `refreshContextUsage()` | 从后端获取精确值 |
| `compressContext()` | 压缩上下文（调用后端 AI 压缩） |
| `refreshStatusPanel()` | 刷新状态面板上下文数据 |
| `renderStatusPanel(usage)` | 渲染状态面板（概览、容量条、占用明细、建议） |

### web/js/sidebar.js — 侧边栏

| 函数 | 作用 |
|------|------|
| `loadSessions()` / `renderSessionList()` | 会话列表 |
| `newSession()` | 新建会话（关联当前 bot，刷新上下文进度条） |
| `switchSession(id)` | 切换会话（恢复 mode 和 working_dir，仅最后 10 条有动画） |
| `deleteSession(id)` | 删除会话 |
| `openFolder()` / `loadFileTree()` / `renderFileTree()` | 文件树 |
| `closeSidebar()` | 关闭侧边栏 |
| `switchSidebarTab(tabName)` | 切换侧边栏面板（chat/files/status） |

### web/js/preview.js — 文件预览

| 函数 | 作用 |
|------|------|
| `previewFile(path)` | 预览文件（含语法高亮、状态栏） |
| `renderPreviewLines(content, lang)` | 渲染行号 + 语法高亮代码（大文件截断 2000 行） |
| `highlightLine(text, lang)` | 单行语法高亮（简易正则实现） |
| `getLang(filename)` | 根据扩展名获取语言标识 |
| `updatePreviewStatus(lines, path, encoding)` | 更新底部状态栏 |
| `showPreviewError(msg)` | 预览错误 |
| `closePreview()` / `copyPreviewContent()` / `sendFileToAI()` | 预览操作 |

### web/js/ops.js — 文件操作

| 函数 | 作用 |
|------|------|
| `parseAndConfirmOperations(aiResponse)` | 解析并确认文件操作（对话模式） |
| `parseAndRenderFileOps(aiResponse, msgElement)` | 解析并渲染文件操作记录块（编程模式） |
| `showConfirmModal(operations)` | 确认弹窗（含 diff 预览） |
| `renderDiff(container, diffText)` | 渲染 diff |
| `executeOperations(ops)` | 执行文件操作 |
| `showRollbackModal()` | 回退弹窗 |

### web/js/providers.js — 供应商设置

| 函数 | 作用 |
|------|------|
| `renderProvidersList()` | 供应商卡片列表 |
| `openProviderDetail(profileId)` | 进入单供应商编辑 |
| `saveProviderDetail()` | 保存供应商配置 |
| `testProviderConnection(profileId)` | 测试连通性 |
| `fetchProviderBalance(profileId)` | 查询余额（支持的端点） |

### web/js/group.js — 群聊

| 函数 | 作用 |
|------|------|
| `loadGroups()` / `renderGroupList()` | 群聊侧边栏列表 |
| `enterGroupSessions(groupId)` | 进入某群的会话列表 |
| `newGroupSession()` | 新建群会话 |
| `showMentionPicker()` | @ 成员选择器 |
| `emergencyStopGroup()` | 急停：中断流式与接话链 |
| `updateGroupComposerUI()` | 群/私聊 composer 显隐（含专家会议按钮） |
| `buildGroupApiMessages()` | 组装群聊 API 消息（成员名前缀） |

### web/js/composer.js — 输入区工具条

| 函数 | 作用 |
|------|------|
| `initComposerToolbar()` | 初始化思考模式/技能芯片 |
| `refreshComposerToolbar()` | 刷新工具条状态 |
| `scheduleComposerSkillsSave()` | 防抖保存技能开关 |

### web/js/memory.js — 记忆库面板

| 函数 | 作用 |
|------|------|
| `refreshMemoryPanel()` | 刷新 entries/items/docs 列表 |
| `openMemoryFolder()` | 打开记忆文件夹 |

### web/js/code-editor.js — 编程模式编辑器

| 函数 | 作用 |
|------|------|
| `openCodeEditor(path, content, options)` | 打开可编辑文件 |
| `saveCurrentEditorFile()` | 保存当前编辑文件 |
| `initCodeEditor()` | 初始化编辑器事件 |

### web/js/code-layout.js — 编程模式布局

| 函数 | 作用 |
|------|------|
| `initCodeLayout()` | 初始化面板拖拽与宽度持久化 |
| `onCodeModeChange(mode)` | 切换 chat/code 时应用布局 |

### 消息 DOM 结构

```
.message-row.user / .message-row.assistant
├── .avatar                 ← 头像 emoji（user 用 user_avatar，AI 用 bot.avatar）
└── .message-bubble
    ├── .thinking-area      ← thinking 块容器（与 content 并列）
    │   └── .thinking-block ← 折叠时只有 header，展开时动态创建 .thinking-content
    │       ├── .thinking-header
    │       │   ├── .thinking-toggle
    │       │   └── .thinking-copy-btn  ← 复制思考内容
    │       └── .thinking-content  ← 仅展开时存在（字体大小由 thinking_font_size 控制）
    ├── .message-attachments ← 附件区域（仅 user 有附件时显示）
    │   ├── .msg-attach-image  ← 图片附件（缩略图+文件名+大小）
    │   └── .msg-attach-file   ← 文件附件（图标+文件名+大小）
    ├── .message-content    ← 正文内容（user-select: text，可选中复制）
    └── .msg-actions        ← 操作栏（始终可见）
        ├── .msg-action-btn  "📋 复制"
        ├── .msg-action-btn  "↻ 重新回答"  （仅 assistant 最新版本显示）
        └── .version-nav    ← 版本导航（仅多版本时显示）
            ├── button "◀"
            ├── span "1/3"
            └── button "▶"

.message-row.error          ← 错误消息（无头像，左侧缩进对齐）
└── .message-content
```

**版本导航：** 重新生成时保留旧版本到 `row._versions` 数组，用 ◀ 1/3 ▶ 切换查看。非最新版本时隐藏「重新回答」按钮。

**入场动画：** `.message-row.animate-in` 带 `fadeInUp` 动画。切换会话时仅最后 10 条消息添加此 class，避免大量消息时动画过慢。

---

## config.json 结构

完整模板见根目录 `config.example.json`。摘要如下：

```json
{
    "api_profiles": [ { "id", "name", "base_url", "api_key", "model", "provider", "temperature", "max_tokens", "max_context", "models", "enabled" } ],
    "bots": [ { "id", "name", "avatar", "profile_id", "soul_folder", "model", "temperature", "max_tokens", "max_context", "thinking_enabled", "thinking_depth", "web_search", "skills_use_global", "enabled_skills" } ],
    "active_bot_id": "default",
    "user_avatar": "😎",
    "context_rounds": 10,
    "auto_save_history": false,
    "user_font_size": 14,
    "bot_font_size": 14,
    "thinking_font_size": 12,
    "receive_dir": "",
    "theme": "dark",
    "api_log_enabled": false,
    "editor_word_wrap": true,
    "enabled_skills": [],
    "web_search_provider": "bing_local",
    "web_search_api_key": "",
    "web_search_max_rounds": 3,
    "web_search_max_queries_per_round": 3,
    "memory_enabled": true,
    "memory_retrieval_enabled": true,
    "memory_write_enabled": true,
    "memory_auto_extract": false,
    "memory_token_budget": 1200,
    "memory_extract_threshold_pct": 85,
    "compress_summary_detail": "standard",
    "memory_organizer_enabled": false,
    "memory_organizer_profile_id": "",
    "memory_organizer_bot_id": ""
}
```

**全局字段（根级）：**

| 字段 | 说明 |
|------|------|
| `context_rounds` | 保留字段，当前**未**用于截断 API 消息（实际发送全部非 system 历史） |
| `auto_save_history` | 是否自动持久化会话 |
| `theme` | UI 主题（如 `dark`） |
| `api_log_enabled` | 是否输出 API 调试日志 |
| `editor_word_wrap` | 编程模式编辑器自动换行 |
| `web_search_*` | 联网 provider、Key、轮次与每轮查询上限 |
| `memory_*` | 记忆总开关、读写、预算、自动压缩阈值等 |
| `compress_summary_detail` | 默认压缩摘要档位：`brief` / `standard` / `detailed` / `max` |

**Bot 可选字段（除示例外）：** `max_context` 可写在 bot 上，覆盖 profile 的 `max_context`。

**Bot 与 Profile 分离：**
- `api_profiles` 负责「怎么连」：地址、密钥、默认模型、上下文上限
- `bots` 负责「是谁」：头像、灵魂文件夹、可覆盖的模型和参数
- 一个 API Profile 可以被多个 Bot 引用
- 每个 Bot 有独立的 `soul_folder`，人设完全隔离

**Bot 参数优先级：**
1. Bot 自身设置（bot.temperature, bot.model, bot.max_tokens）
2. Profile 默认值（profile.temperature, profile.model, profile.max_tokens）
3. 全局默认值（temperature=0.7, max_tokens=4096）

**旧格式兼容：** 启动时检测无 `bots` 字段，自动迁移：
1. 创建默认 bot，引用原 active_profile_id
2. 在 MeClaw 目录下创建 `souls/default/` 文件夹
3. 将原 system_prompt 写入 `souls/default/soul.md`
4. 如有旧 soul_folder，复制内容到 `souls/default/`
5. 删除旧字段（system_prompt, soul_folder, active_profile_id）

---

## 关键约束

| 项目 | 说明 |
|------|------|
| pywebview 版本 | 必须用 5.3.1（6.x 有递归溢出 bug） |
| Python 版本 | 3.11+（当前环境 3.12） |
| 文件大小限制 | 超过 50KB 或 1000 行截断 |
| 编码检测 | utf-8 → gbk → 返回乱码通知 |
| 路径安全 | 所有文件操作必须在工作目录内 |
| 备份目录 | .meclaw_backup/ 在工作目录下 |
| API 内省 | `__dir__` 排除 window，防止 pywebview 卡死 |
| history 目录 | 与 config.json 同级 |
| souls 目录 | 与 config.json 同级，每个 bot 一个子文件夹 |
| 灵魂文件夹 | soul.md → constraints.md → memory.md → knowledge/ → 其他 .md |
| 上下文控制 | system + 摘要 + 全部对话历史（始终发送全部） |
| memory.md | 灵魂文件夹中唯一可被 AI 写入的文件 |
| file:send 格式 | `<!--file:send:path=...-->` HTML 注释格式，避免与代码块冲突 |
| 接收目录 | 默认 MeClaw/downloads/，不存在时自动创建，设置面板可配置 |
| AI 文件历史 | 只存路径和元信息，不存 base64，加载历史时显示文件信息卡片 |
| provider | `generic` / `deepseek` / `anthropic`，存在 api_profiles 中 |
| DeepSeek 思考模式 | `reasoning_effort` + `extra_body.thinking`，不发送 temperature |
| reasoning_content 回传 | 有 file: 操作的消息必须保留，否则 DeepSeek 400 报错 |
| 最少 1 个 bot | 删除 bot 时检查，只剩一个不允许删除 |
| bot 参数覆盖 | bot 中为空/null 的字段使用 profile 的值 |
| max_context | `bot.max_context` 优先，否则 `profile.max_context` |
| soul_folder 路径 | 推荐 `souls/{bot-id}` 相对应用根目录；运行时经 `resolve_app_path()` 解析 |
| soul.md 命名 | 必须小写 `soul.md`（非 `SOUL.md`），否则不进「身份与人格」优先级 |
| 上下文满禁用 | percentage >= 100 时禁用发送按钮，sendMessage 守卫拦截 |
