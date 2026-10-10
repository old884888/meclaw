## Why

`LearnerBrain` 已能收集 signal 与保存 candidate，但缺少「何时值得复盘」的触发策略，仍是空转收件箱。Hermes Nudge 机制：用户纠正、多轮修任务、任务完成踩坑 → 后台 Review。本提案在不破坏「只产候选、不改 soul」安全基线的前提下，激活 learner 的第一环。

## What Changes

- 定义 signal 分类与 trigger 规则（纠正、多轮修订、任务完成、topic _burst）
- turn 完成后异步 classify → 命中则 enqueue review job
- Review job 产出 pending candidate：`l3_profile_update` | `skill_draft` | `prompt_hint`
- 配置：`learner_nudge_enabled`, trigger 阈值
- UI：候选列表（可后续）；本提案 API 先就绪

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `mnemos-learner-brain`: SHALL classify turn signals and enqueue review jobs when nudge triggers match.

## Impact

- 后端：`learner_brain.py`、新 `nudge/` 模块、`main.py` post-turn hooks
- 不增加实时 prompt token
- 为 `mnemos-skill-memory` 提供 skill_draft 候选来源
