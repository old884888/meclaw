## Context

MeClaw 使用 pywebview + 静态前端。当前：

- 思考模式：`bot.thinking_enabled` / `bot.thinking_depth`，仅在编辑机器人弹窗配置；`api.py` 发 DeepSeek 请求时读取。
- 技能：全局 `config.enabled_skills` + Bot 级 `skills_use_global` / `enabled_skills`；`build_system_prompt()` 合并技能指令。
- 输入区：`#input-area` 含 `input-row`（附件、textarea、发送/停止）；编程模式有 `#code-mode-bar` 新任务。
- 顶栏 `#current-bot-mode-badge` 与状态面板只读展示模式。

用户希望在发消息前于输入区完成上述配置，避免进入多层弹窗。

## Goals / Non-Goals

**Goals:**

- 两行 composer 布局（工具条 + 输入行）
- DeepSeek 下快速/思考/深度切换并写回当前 Bot
- 技能 popover（全局为主，自定义 Bot 有明确路径）
- 与 `updateBotDisplay`、`refreshConfig`、切换 Bot 同步

**Non-Goals:**

- 单条消息临时覆盖思考模式（会话级 override，留 v2）
- 重做编辑机器人或设置页内的完整技能/思考 UI（保留为完整配置入口）
- 非 DeepSeek provider 的 thinking API 扩展

## Decisions

### 1. 持久化策略：写回当前 Bot（方案 A）

切换工具条即更新 `cachedConfig` 中 active bot 并调用现有 `save_bot`（可抽 `saveActiveBotThinking(fields)` 减少 payload）。

**理由**：与顶栏徽章、状态面板、后端 `send_message` 一致，无需改 API 契约。  
**备选**：仅前端会话状态 — 被拒，会与编辑页配置不一致。

### 2. 模块划分：新增 `web/js/composer.js`

工具条渲染、事件、popover 逻辑集中于此；`bot.js` 保留 `getDeepSeekReplyMode`、`formatReplyModeStatus`；`app.js` 在 `pywebviewready`、`switchBot` 后调用 `refreshComposerToolbar()`。

**理由**：避免 `app.js` 继续膨胀。  
**备选**：全部塞进 `bot.js` — 可行但职责混杂。

### 3. HTML 结构

```html
<div id="input-area">
  <div id="attachments-preview" ...></div>
  <div id="code-mode-bar" ...></div>
  <div id="composer-toolbar" class="composer-toolbar hidden">
    <div class="composer-toolbar-group" data-group="thinking">...</div>
    <div class="composer-toolbar-group" data-group="skills">...</div>
  </div>
  <div class="input-row">...</div>
</div>
```

思考组默认对非 DeepSeek `display:none`（或 JS 不渲染）。深度控件嵌在思考组内，仅 `thinking_enabled` 时显示。

### 4. 技能 Popover

- 点击「技能 · N 项」展开绝对定位面板，列表复用与设置页相同的 `renderSkillList(listId, emptyId, enabledIds)`（将函数提升到 `bot.js` 或 `utils` 层导出）。
- 全局：勾选变更 → `save_config` 仅 `enabled_skills` 字段（或全量 `cachedConfig`）。
- 自定义 Bot：popover 顶部提示 + 链式 `showBotEditModal`；或在 popover 内用 `bot-skill-list` 勾选后 `save_bot`。

**决策**：自定义 Bot 在 popover 内直接勾选并 `save_bot`，与全局分支共用 UI，减少跳转。

### 5. 样式

- Chip 按钮复用 `.toggle-btn` / 新 `.composer-chip`，高度 28–32px，与 `#input-area` 圆角容器协调。
- 窄屏：工具条 `flex-wrap`，避免挤压输入框。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 频繁 `save_bot` 写盘 | 切换模式时单次保存；深度切换 debounce 300ms |
| 与编辑弹窗同时改 Bot 配置 | 保存 bot 后统一 `refreshComposerToolbar()` |
| 自定义技能与全局技能 UI 混淆 | Popover 标题标明「全局」或「仅此 Bot」 |
| `save_bot` 新建 bot 时 soul 路径绝对化 | 工具条仅更新已有 active bot |

## Migration Plan

1. 纯前端 + 既有 `save_bot` / `save_config`，无数据迁移。
2. 部署后用户重启 MeClaw；旧 `config.json` 已含 `enabled_skills` / `skills_use_global` 字段。
3. 回滚：移除 toolbar DOM/JS，恢复单行 input-row。

## Open Questions

- 自定义 Bot 技能是否在 popover 内编辑即可，还是必须跳转编辑页？（当前设计：popover 内可编辑）
- 是否在工具条显示当前 API 名称？（暂不，顶栏已有 Bot/模型信息）
