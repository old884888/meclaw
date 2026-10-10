## Context

MeClaw 已有两个相关能力：

- **单 AI 专家模式**（`backend/expert_mode.py`）：一个模型顺序走三幕（解构→发散→收敛），通过 `<scratchpad>` 草稿纸跨阶段传递，按阶段流式推送（stage1/2 → 思考区，stage3 → 回答区），结果落 `memory/scratchpad.md`。局限：单模型自我锚定、无证伪、草稿纸靠模型整块重写易丢信息。
- **群聊**（`backend/groups.py`、`backend/group_mentions.py`）：多个真实 Bot，用户 @ 才回复，`auto_interaction_enabled` 时按概率自动 @ 与接话链（`compute_chain_queue` / `postprocess_group_assistant`），群记忆在 `groups/{id}/memory/`，前端 `web/js/group.js` 串行渲染。

本变更参考《多 Agent 专家组协作协议（认知议会模型）》，把群聊成员编排成回合制专家组，复用单 AI 专家模式的流式推送骨架与群聊的成员/记忆基础设施，新增共享黑板与角色机制。

## Goals / Non-Goals

**Goals:**

- 在群聊会话上提供回合制「专家会议」运行模式：独立诊断 → 交叉澄清 → 红队攻击 → 架构师整合，可选人类仲裁后执行细化。
- 用结构化共享黑板替代「整块重写草稿纸」，做到冻结+追加、带版本号、作为后续轮次唯一上下文来源以控 token。
- 复用现有逐轮/逐 token 流式推送与群聊渲染，让会议过程可见、可审计。
- 会议产出共识快照落群记忆，可被后续检索。
- 与现有自由接话模式互斥共存，不破坏既有群聊行为。

**Non-Goals:**

- 不实现完整 6 层流水线与 Agent 间异步消息总线；先做 MVP（4 轮 + 可选执行细化）。
- 不做真正并行 HTTP 调用（Round 1 逻辑独立即可，实现上可串行调用，关键是 prompt 隔离反锚定）。
- 不改单 AI 专家模式的对外行为（仅抽取可复用工具函数）。
- 不引入新的第三方依赖。

## Decisions

### D1. 新建 `backend/expert_council.py`，复用 `expert_mode` 的调用骨架

会议编排独立成模块，避免把群聊与单 AI 专家逻辑耦合进 `expert_mode.py`。从 `expert_mode.py` 抽出可复用的单轮流式调用（`_expert_api_call` 思路）为共享 helper，会议各轮调用它。
- 备选：直接扩 `expert_mode.py`。否决：职责膨胀、群聊/私聊分支混杂。

### D2. 角色映射到成员 Bot + 兜底 persona

会议角色 = {专家组(全体或选定成员)、红队、架构师}。优先用成员自身 `soul.md`；缺红队/架构师角色时用内置临时 persona（类似单 AI 专家的 `STAGE_SYSTEM`），并在输出标注「系统角色」。红队尽量批判非自己作者的草案。
- 备选：强制要求建群时指定角色。否决：增加使用门槛，且小群人数不足。

### D3. 共享黑板：结构化字段 + 程序化追加

黑板为后端内存中的结构化对象（dataclass / dict），字段 `Current_Consensus / Open_Divergences / Falsified_Hypotheses / Key_Constraints / Context_Version`。每轮结束，由一个「记录者」调用解析本轮产出并**追加/修正字段**，而非让模型重写整块；`Context_Version += 1`。注入后续轮次时序列化为简短文本块。
- 这是对单 AI 专家草稿纸「整块覆盖」缺陷的修正（见 proposal）。
- 备选：沿用 `<scratchpad>` 整块覆盖。否决：早期共识易被模型悄悄改写丢失。

### D4. 反锚定通过 prompt 隔离实现

Round 1 每个专家 Bot 的 messages 只含题目 + 自身 persona，不含其他专家草案。Round 2 把草案匿名化（去掉作者名，编号 A/B/C）后分发，且 prompt 限定「只准提澄清性问题」。
- 实现上 Round 1 可串行多次调用，互不传递上下文即满足「互相不可见」。

### D5. 逐轮 + 逐 token 推送，复用前端流式

后端每轮、每个 Bot 发言通过类似 `onExpertStage` / `onToken` 的回调推送；前端在群聊气泡内按「轮次分组 + Bot 标识」渲染，黑板快照可点开查看（复用草稿纸浮层样式）。最终架构师推荐作为该会话的一条 assistant 消息存库。
- 备选：等全部完成再一次性返回。否决：长会议无反馈、不可审计、与现有体验不一致。

### D6. 与自由接话互斥；会议状态挂在「这一次运行」上

会议由用户在群 composer 开「专家会议」开关触发，作用于当轮。运行期间不跑 `compute_chain_queue` 的概率链；`auto_interaction_enabled` 配置不变，会议结束后自动恢复自由接话。会议轮数受会议自己的上限约束，不消耗 `max_chain_rounds`。

### D7. 成本上限与上下文压缩

每次会议模型调用数 ≈ 专家数×Round1 + Round2(交叉) + Round3 + Round4，需设可配置 `council_max_experts` 与 `council_max_rounds`；从 Round 2 起只发黑板快照 + 本轮输入。分歧僵持超阈值（默认 2 轮）冻结升级给用户仲裁，不再空耗。

## Risks / Trade-offs

- [成员数×轮数导致 token/时延暴涨] → Mitigation：限制参与专家数与轮数；Round 2+ 只发黑板快照；提供停止按钮保留已产出。
- [小模型不遵守角色/格式（不输出置信度、红队"只破不立"以外乱发言）] → Mitigation：强格式 prompt + 解析兜底（缺字段给默认值）；红队/架构师可用更强的 organizer profile。
- [黑板解析失败导致共识丢失] → Mitigation：解析失败时保留上一版黑板并标记告警，绝不清空；版本号可回看。
- [反锚定在串行实现下仍可能因共享会话上下文泄漏] → Mitigation：Round 1 每次调用构造独立 messages，不带其他专家产出。
- [与现有群聊接话链状态冲突] → Mitigation：会议运行期显式短路概率链；会议结束统一恢复。
- [群成员 persona 与专家角色冲突（人设抢戏）] → Mitigation：角色 system 段置于 persona 之后并明确「本轮以 X 角色协作」。

## Resolved Decisions（已确认）

- **专家组参与**：默认全体成员；超过 `council_max_experts`（默认 5）时由用户在会议启动前勾选参与者。
- **红队/架构师指派**：群设置 `council_red_team_bot_id` / `council_synthesizer_bot_id` 可选固定指派；留空则每次临时分配，仍缺则系统兜底 persona。
- **执行细化轮**：Round 4 后默认停在人类仲裁；仅当用户点「深化」才跑执行细化轮。
- **共识快照格式**：复用 `memory/entries/` Markdown 结构，`type: council` 标记，便于检索与区分。
