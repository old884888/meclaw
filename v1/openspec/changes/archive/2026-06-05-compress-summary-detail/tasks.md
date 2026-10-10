## 1. 后端：摘要详略模板与 API

- [x] 1.1 新建 `backend/memory/compress_prompts.py`：四档 `minimal` / `standard` / `detailed` / `max` 的 summary prompt 模板
- [x] 1.2 `compress_context(direction, detail_level=None)`：解析档位（bot 覆盖 → 全局 → standard），组装 prompt（模板 + 压缩方向）
- [x] 1.3 `config` / `DEFAULT_CONFIG` 增加 `compress_summary_detail`；`bots[]` 可选覆盖；迁移缺省为 `standard`
- [x] 1.4 自动压缩 `_try_auto_compress` 使用解析后的默认档位（不传弹窗值）

## 2. 后端：max 档记忆增强（可选 quote）

- [x] 2.1 `memory/extractor.py`：`detail_level == max` 时使用增强 extraction prompt（最多 3 条 `quote`）
- [x] 2.2 `compress_context` 将 `detail_level` 传入 `run_memory_extraction`
- [x] 2.3 保持 fact/preference 短条目与质量过滤不变

## 3. 前端：压缩弹窗 UI

- [x] 3.1 `index.html` 压缩弹窗增加「摘要详略」四档单选（极简 / 标准 / 详尽 / 琐碎 max）
- [x] 3.2 琐碎 max 旁显示 form-hint：摘要更长、占用更多上下文
- [x] 3.3 `app.js` 确认压缩时传 `detail_level` 给 `compress_context`
- [x] 3.4 压缩进行中禁用确认按钮（与现有 `compressInProgress` 一致）

## 4. 配置 UI（可选）

- [x] 4.1 设置 → 记忆：全局默认摘要详略下拉
- [x] 4.2 Bot 编辑：可选「摘要详略 · 跟随全局 / 自定义」与下拉（与 `compress_summary_detail` 字段对齐）

## 5. 文档与验证

- [x] 5.1 更新 `docs/记忆系统使用帮助.md`：摘要详略四档说明、与 items/收藏的分工
- [ ] 5.2 手动验证：四档摘要长度差异可见；标准档与现网行为一致
- [ ] 5.3 手动验证：详尽/琐碎 max + 压缩方向叠加；max + 记忆写入可产生 quote（若有金句）
- [ ] 5.4 手动验证：自动压缩使用 Bot/全局默认档位
