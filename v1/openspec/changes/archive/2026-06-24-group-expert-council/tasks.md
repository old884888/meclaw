## 1. 复用骨架抽取

- [x] 1.1 从 `backend/expert_mode.py` 抽出可复用的单轮流式调用 helper（基于 `_expert_api_call`），供会议各轮共用
- [x] 1.2 抽出置信度/基础字段解析工具（`Confidence`/`Basis`），缺失时给默认值
- [x] 1.3 将「冻结+追加」式草稿纸思路提炼为通用工具（供单 AI 专家与会议共用），不改单 AI 专家对外行为

## 2. 共享黑板（shared-blackboard）

- [x] 2.1 新增黑板数据结构：`Current_Consensus / Open_Divergences / Falsified_Hypotheses / Key_Constraints / Context_Version`
- [x] 2.2 实现初始化（版本号=1，空列表）
- [x] 2.3 实现每轮「追加/修正」更新（版本号+1，不整块重写），解析失败时保留上一版并标记告警
- [x] 2.4 实现黑板序列化为简短注入文本块（供 Round 2+ 上下文）
- [x] 2.5 实现分歧冻结：同一分歧持续超阈值（默认 2）标记 `Escalated_Dispute` 并上报仲裁

## 3. 会议编排核心（backend/expert_council.py）

- [x] 3.1 新建 `backend/expert_council.py` 模块与 `run_council_pipeline` 入口
- [x] 3.2 角色分配：成员映射 + 缺角色兜底临时 persona（标注系统角色）
- [x] 3.3 Round 1 独立诊断：每专家独立 messages（不含他人草案），强制输出 `Root_Cause/Solution_Draft/Confidence`
- [x] 3.4 Round 2 交叉澄清：草案匿名化分发，限定只提澄清性问题
- [x] 3.5 Round 3 红队攻击：输出每草案失败路径/资源/证伪证据，红队尽量不评自己作者的草案
- [x] 3.6 Round 4 架构师整合：1-3 混合方案 + 决策矩阵 + 单选推荐（禁止"各有优劣"）
- [x] 3.7 人类仲裁停靠点：Round 4 后暂停，等用户选定方向
- [x] 3.8 可选执行细化轮：里程碑/资源预算/风险缓解/验收标准
- [x] 3.9 成本上限：`council_max_experts` / `council_max_rounds`；停止标志中断并保留已产出
- [x] 3.10 完成时写共识快照到 `groups/{id}/memory/entries/`

## 4. 群聊集成与互斥

- [x] 4.1 `backend/group_mentions.py` / `backend/groups.py`：群 meta 增加会议相关字段（可选角色指派、会议上限）
- [x] 4.2 会议运行期短路 `compute_chain_queue` 概率接话链；结束后恢复
- [x] 4.3 `backend/main.py` / `backend/api.py`：会议会话路由、逐轮/逐 token 推送回调、产出存入会话历史
- [x] 4.4 会议消息带 speaker Bot 标识，重开会话可重新渲染

## 5. 前端入口与渲染

- [x] 5.1 `web/js/composer.js` / `web/index.html`：群 composer 增加「专家会议」开关（仅当轮生效，≥2 成员可用）
- [x] 5.2 `web/js/group.js` / `web/js/chat.js`：按「轮次分组 + Bot 标识」渲染会议过程，复用流式回调
- [x] 5.3 黑板快照查看：复用草稿纸浮层样式，可点开看 `Context_Version` 与各字段
- [x] 5.4 仲裁停靠 UI：展示混合方案 + 决策矩阵，提供「选定方向 / 深化 / 结束」操作
- [x] 5.5 置信度/角色标签在发言上展示
- [x] 5.6 `web/style.css`：会议轮次、角色徽章、黑板浮层样式
- [x] 5.7 停止按钮中断会议并保留已产出

## 6. 文档与校验

- [x] 6.1 更新 `docs/系统结构.md`：新增 `expert_council.py`、会议模式、群记忆产出
- [x] 6.2 更新 `docs/API参考.md`：会议相关后端方法与前端回调
- [ ] 6.3 手动验证：≥2 成员群跑通 4 轮 + 仲裁，黑板版本递增、共识快照落库、停止可中断、与自由接话互不干扰
- [x] 6.4 `openspec validate group-expert-council` 通过
