## Why

MeClaw 的深度思考、技能启用等能力目前藏在「编辑机器人」或「设置」里，发消息前无法快速切换；输入区只有附件和发送按钮，与顶栏/状态面板的模式信息重复且不同步。用户希望在对话框（composer）附近一站式完成「怎么发这条消息」的配置，减少来回打开弹窗的操作。

## What Changes

- 在聊天输入区上方增加 **composer 工具条**（控制条 + 原有输入行两行布局）
- 工具条提供 **快速 / 思考** 模式切换与 **思考深度**（high / max），仅当当前 Bot 关联 DeepSeek API 时显示
- 工具条提供 **技能** 入口：popover 勾选全局 `enabled_skills`；若当前 Bot 为「仅此 Bot 自定义」则提示并引导至编辑页或展示 Bot 专属列表
- 切换思考/深度时 **写入当前激活 Bot** 配置（与编辑机器人、顶栏徽章、状态面板一致）
- 切换 Bot 或刷新配置后工具条状态自动同步
- 非 DeepSeek Bot 时隐藏思考相关控件，仅保留技能与输入

## Capabilities

### New Capabilities

- `composer-toolbar`: 输入区 composer 工具条 UI、与 Bot/API 配置的联动、技能 popover、DeepSeek 条件显示

### Modified Capabilities

（无既有 `openspec/specs/` 基线规格，本次为新增能力。）

## Impact

- **前端**：`web/index.html`（`#input-area` 结构）、`web/style.css`、`web/js/bot.js`（保存当前 Bot 思考参数）、`web/app.js` 或新建 `web/js/composer.js`（工具条逻辑）、`web/js/config.js`（技能勾选与全局配置同步）
- **后端**：可选轻量 API `update_active_bot_fields` 或复用现有 `save_bot`；`send_message` / `build_system_prompt` 逻辑不变（仍读 Bot 配置）
- **文档**：与全局技能、`skills_use_global` 行为一致，需在 UI 文案中说明
