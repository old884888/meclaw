## Why

当前「压缩上下文」只有单一摘要风格（偏简洁）和可选自由文本「压缩方向」，用户容易误解「压缩」为越压越短；实际上有人需要**保留更多要点、结构化摘要甚至原话摘录**（尤其长讨论、写作打磨场景），又怕遗漏关键句。需要引入**摘要详略**四档（极简 / 标准 / 详尽 / 琐碎 max），与现有「压缩方向」叠加，只影响会话摘要 `current_summary`，不把 `memory/items` 变成长文。

## What Changes

- 压缩弹窗与状态面板文案：「压缩程度」改为 **摘要详略**（四档单选）
- 四档：`minimal`（极简）、`standard`（标准，默认）、`detailed`（详尽）、`max`（琐碎 max）
- 后端 `compress_context(direction, detail_level)`：按档位选择不同 `compress_prompt` 模板；**压缩方向**仍作为用户补充约束叠加
- 配置持久化：全局默认 `compress_summary_detail`（标准），可选 per-bot 覆盖；手动压缩使用弹窗所选档位
- 自动压缩（85% 触发）使用 Bot/全局默认档位，不在发消息前弹窗
- **琐碎 max** 档位：摘要允许更多 bullet、分话题小节、摘录少量原话金句；UI 提示「占用上下文更多」
- 记忆整理（`memory_extraction`）**默认逻辑不变**（短条目）；max 档可选增强：多提取 0～3 条 `quote` 到 `items/quote/`（受现有质量过滤）
- 更新 `docs/记忆系统使用帮助.md` 中压缩相关说明

## Capabilities

### New Capabilities

- `compress-summary-detail`: 摘要详略四档、prompt 模板、配置与压缩 UI、与 `compress_context` API 集成

### Modified Capabilities

- `bot-memory`: max 档压缩时可选「金句摘录」增强记忆整理（仍写 `items/quote/`，不拉长 fact 条目）

## Impact

- **后端**：`backend/main.py`（`compress_context`、prompt 模板、配置读取）；`backend/memory/config.py` 或 `api.py` 默认配置迁移
- **前端**：`web/index.html`（压缩弹窗四档 UI）；`web/app.js`（传 `detail_level`）；`web/js/config.js` / `web/js/bot.js`（默认档位设置，可选）
- **配置**：`config.example.json` 增加 `compress_summary_detail`；`bots[]` 可选 `compress_summary_detail` 覆盖
- **文档**：`docs/记忆系统使用帮助.md`
- **无新依赖**
