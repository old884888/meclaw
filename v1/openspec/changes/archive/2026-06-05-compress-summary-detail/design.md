## Context

MeClaw 已有 `compress_context(direction)`：将旧对话压成 `current_summary` 并可选运行 `memory_extraction`。默认 prompt 要求「简洁摘要」，用户反馈「压缩程度高」命名反直觉（详尽档反而内容更多），且长讨论中 5～6 个要点/金句易在短 `items` 中丢失。会话摘要与中期记忆分层：`current_summary` 承载本场脉络；`items/` 保持短条目可检索。

## Goals / Non-Goals

**Goals:**

- 压缩 UI 提供 **摘要详略** 四档：极简 / 标准 / 详尽 / 琐碎 max
- 档位仅改变 **会话摘要 prompt 模板**；与现有「压缩方向」自由文本叠加
- 全局默认 + 可选 per-bot 覆盖；自动压缩使用默认档位
- max 档在记忆整理阶段**可选**多写 0～3 条 `quote`（仍过质量过滤）
- 文档更新，避免「压缩=越短」误解

**Non-Goals:**

- 不把 `memory/items` 默认改为长文存储
- 不改变 FTS 检索算法
- 不为摘要做流式进度 token 计数
- 不新增向量库或二次模型 merge

## Decisions

### 1. 命名与档位枚举

| UI 标签 | 内部值 | 摘要策略 |
|---------|--------|----------|
| 极简 | `minimal` | 3～6 bullet，删寒暄，最短 |
| 标准 | `standard` | 当前默认行为 |
| 详尽 | `detailed` | 结构化：背景 / 要点 / 结论 / 待定 |
| 琐碎 max | `max` | 分话题多要点，允许 3～8 句原话摘录，更长但仍禁止整段粘贴 |

**理由**：用「详略」而非「压缩程度」，与用户心智一致。`max` 单独命名避免与思考模式 `max` 混淆——上下文用 `compress_summary_detail=max`，与 `thinking_depth` 无关。

### 2. Prompt 组装

```text
base_template(detail_level)
+ 用户压缩方向（若有）
+ 旧对话正文
```

模板放在 `backend/memory/compress_prompts.py`（或 `backend/main.py` 内常量表），便于单测与文档对照。

### 3. API 签名

`compress_context(direction="", detail_level=None)`：

- `detail_level` 为空时解析：bot 覆盖 → 全局 `compress_summary_detail` → `standard`
- 前端手动压缩传弹窗所选；自动压缩不传，用默认

### 4. 配置

- `config.json`: `compress_summary_detail`: `"standard"`
- `bots[]`: 可选 `compress_summary_detail` 覆盖
- 设置 → 记忆 或压缩相关卡片：默认档位下拉（可选实现于 tasks 2.x）

### 5. max 档记忆增强（可选子步骤）

当 `detail_level == "max"` 且 memory write 开启时，`run_memory_extraction` 使用增强 prompt 附录：允许最多 3 条 `quote`（`importance≥4`），仍走 `is_low_quality` / 去重。fact/preference 条数上限仍为 8。

**替代方案**：摘要与记忆共用 max 长 prompt——否决，易把长文写入 items。

### 6. UI

压缩弹窗：四档单选（默认记住上次选择于 `sessionStorage` 或全局配置）；琐碎 max 旁注「摘要更长，占用更多上下文」。

## Risks / Trade-offs

- **[Risk] max 摘要膨胀占满上下文** → 弹窗提示 + 状态面板摘要 token 在 `calc_context_usage` 已可见；文档建议编程长会话用详尽而非 max 常驻
- **[Risk] 与 thinking 模式叠加更慢** → 压缩本就非流式；不在本变更优化
- **[Risk] quote 自动提取质量参差** → 仅 max 档启用；低置信度过滤；用户仍可 ⭐ 手动收藏

## Migration Plan

1. 部署后 `compress_summary_detail` 默认 `standard`，行为与现网一致
2. 无数据迁移；旧会话摘要保留
3. 回滚：移除档位参数，回退单一 prompt

## Open Questions

- 是否在 Bot 编辑页暴露默认档位（proposal 标为可选）——tasks 中作为 2.x 可选任务
- 琐碎 max 是否在自动压缩时禁用（仅手动）——当前设计：自动压缩跟随 Bot/全局默认，用户可将默认设为 standard 避免自动 max
