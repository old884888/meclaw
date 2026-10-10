# Tasks — expert-mode-redesign

## 1. 移除 Bot 设置中的专家模式

- [ ] 1.1 `web/index.html`：移除 bot 编辑器中的专家模式 section
- [ ] 1.2 `web/js/bot.js`：移除 `expert_mode_enabled` 相关的 toggle 和 save 逻辑
- [ ] 1.3 `web/js/bot.js`：移除 Header 的专家模式 badge（`expert-mode-badge`）
- [ ] 1.4 `backend/api.py`：移除 `_call_api` 中的专家模式拦截逻辑

## 2. 输入框旁的临时开关

- [ ] 2.1 `web/index.html`：在发送按钮左侧增加 🎯 按钮（`btn-expert-mode`）
- [ ] 2.2 `web/js/chat.js`：`toggleExpertMode()` 函数，切换按钮高亮状态
- [ ] 2.3 `web/js/chat.js`：`sendMessage()` 中检测专家模式按钮状态，传递给后端
- [ ] 2.4 `web/style.css`：专家模式按钮样式（高亮时蓝色）

## 3. 后端逐 Stage 推送

- [ ] 3.1 `backend/expert_mode.py`：重构 `run_expert_pipeline`，每完成一个 Stage 推送内容到前端
- [ ] 3.2 `backend/expert_mode.py`：新增 `onExpertStage` 事件，包含 stageId、content、scratchpad
- [ ] 3.3 `backend/api.py`：`send_message` 中检测 `expert_mode` 参数，调用 pipeline
- [ ] 3.4 `backend/api.py`：确保 pipeline 完成后调用 `onStreamDone`

## 4. 前端 Stage 渲染

- [ ] 4.1 `web/js/chat.js`：`onExpertStage(payload)` handler，在 AI 消息气泡内追加 Stage 区块
- [ ] 4.2 `web/js/chat.js`：Stage 区块默认折叠，点击展开显示完整内容
- [ ] 4.3 `web/js/chat.js`：Stage 进行中显示 spinner，完成显示 ✓
- [ ] 4.4 `web/js/chat.js`：最终结论渲染在 Stage 区块下方，用分割线隔开
- [ ] 4.5 `web/style.css`：Stage 区块样式（带左侧竖线、展开/折叠动画）

## 5. 草稿纸浮层

- [ ] 5.1 `web/js/chat.js`：在 Stage 区块旁增加"查看草稿纸"按钮
- [ ] 5.2 `web/js/chat.js`：点击后显示浮层/抽屉，展示当前草稿纸内容
- [ ] 5.3 `web/style.css`：草稿纸浮层样式

## 6. 清理

- [ ] 6.1 移除 Header 中的 `expert-mode-badge` HTML
- [ ] 6.2 移除 `backend/expert_mode.py` 中不再需要的 `EXPERT_PROTOCOL` 常量
- [ ] 6.3 确保 Bot 切换时专家模式按钮状态重置
