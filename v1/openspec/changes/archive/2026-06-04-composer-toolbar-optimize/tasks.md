## 1. 结构与样式

- [x] 1.1 在 `web/index.html` 的 `#input-area` 内增加 `#composer-toolbar`（思考组、深度组、技能按钮、技能 popover 容器）
- [x] 1.2 在 `web/style.css` 添加 `.composer-toolbar`、`.composer-chip`、`.skills-popover` 样式（含换行与 z-index）
- [x] 1.3 新建 `web/js/composer.js` 并在 `index.html` 引入（位于 `bot.js` 之后、`app.js` 之前）

## 2. 工具条状态与 DeepSeek 模式

- [x] 2.1 实现 `refreshComposerToolbar()`：根据 active bot + profile 显示/隐藏思考组与深度组
- [x] 2.2 绑定「快速 / 思考」chip，切换时更新 `cachedConfig` 并调用 `save_bot`（仅 thinking 字段）
- [x] 2.3 绑定「标准 high / 加深 max」chip，写回 `thinking_depth`（可选 debounce）
- [x] 2.4 在 `switchBot`、`updateBotDisplay`、`saveBot` 成功后调用 `refreshComposerToolbar()`

## 3. 技能 Popover

- [x] 3.1 将 `renderSkillList` / `collectEnabledSkillIds` 调整为可传入 listId（或抽到共享函数供设置页与 composer 复用）
- [x] 3.2 技能按钮展示已启用数量；点击打开 popover
- [x] 3.3 全局 Bot：勾选变更后 `save_config` 更新 `enabled_skills`
- [x] 3.4 自定义 Bot：popover 内勾选并 `save_bot` 更新 `enabled_skills` + `skills_use_global: false` 提示文案

## 4. 集成与验证

- [x] 4.1 `pywebviewready` 与打开设置保存后刷新 composer 技能摘要
- [x] 4.2 手动验证：DeepSeek Bot 切换思考/深度后发送消息、顶栏徽章与状态面板一致
- [x] 4.3 手动验证：非 DeepSeek Bot 不显示思考控件；技能全局/自定义两路径可用
