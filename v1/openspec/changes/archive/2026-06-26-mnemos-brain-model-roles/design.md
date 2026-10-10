## Context

现状只有 `executor` 与 `background` 两档模型（`main._profile_for_bot(role=...)`、`config_store` 的 `background_model`）。L1 提取（`l1_extractor`）、Tier3 摘要（`tier3_summarizer`）共用 background；embedding（P1）、rerank（P2）此前无统一配置位。本提案把「模型角色」抽象为可绑定 + 可回退的统一体系，既服务对话/后台任务，也作为 P1/P2 的配置入口，消除配置碎片化。

## Goals / Non-Goals

**Goals:**

- 定义角色集：`executor` / `extraction` / `summary` / `embedding` / `rerank`。
- 每角色「provider profile + model」可绑定；空绑定走确定性回退链。
- 全局默认 + Bot 覆盖（复用现有 `brains` 覆盖）。
- 统一「按角色解析模型」解析器，替换零散二分逻辑，**默认零行为变化**。
- 最小可用 UI（Bot 编辑器角色区）+ 状态面板展示实际模型。

**Non-Goals:**

- 不实现 embedding/rerank 本体（分别在 P1/P2）；本提案只提供其配置位与解析。
- 不改记忆/检索算法。
- 不做多模型负载均衡 / 路由智能选择（未来）。

## Decisions

### D1：角色解析器 `resolve_model(bot, role)`

集中到一处（`main.py` 或新 `model_roles.py`）：

```
resolve_model(bot, role):
  binding = bot_override(role) or global_role(role)
  if binding: return profile+model
  # fallback chain
  if role in (extraction, summary): return background or executor
  if role == executor: return executor
  if role in (embedding, rerank): return None  # 由各自端口按自身 provider/off 处理
```

**为何集中**：现有 `role="executor"/"background"` 分散在多处；统一后 P1/P2/状态面板都调它，行为一致、易测。

### D2：配置结构

`config` 增加 `model_roles`（全局默认）：

```
model_roles: {
  executor:   {profile_id, model},
  extraction: {profile_id, model} | null,
  summary:    {profile_id, model} | null,
  embedding:  {provider, model} | null,   # 与 P1 对齐
  rerank:     {provider, model} | null,   # 与 P2 对齐
}
```

Bot 级 `brains.model_roles` 覆盖同结构子集。归一时空值表示「继承/回退」。

**向后兼容**：保留旧 `background_model` 读取；若 `model_roles.extraction/summary` 未配则用旧 background。迁移期两者并存，解析器优先 roles、回退 background。

### D3：UI（最小）

Bot 编辑器「大脑」区下加「模型角色」分组：executor/extraction/summary 三个下拉（embedding/rerank 待 P1/P2 接入后再显）。状态面板 `brain_status` 增加各角色实际解析到的模型展示。

### D4：分阶段接入

本提案先落 executor/extraction/summary（有真实消费方），embedding/rerank 角色**先作为配置占位**（有绑定但无实现时等同 disabled），等 P1/P2 合入后接上，无需再改配置结构。

## Risks / Trade-offs

- [配置结构变更引入迁移风险] → 解析器优先 roles、回退旧 background；旧配置零改动可用。
- [UI 角色过多让用户困惑] → 默认只显 3 个有实现的角色；其余留空=继承，文案标注「留空继承」。
- [Bot 覆盖与全局合并复杂] → 复用现有 `brains_config_for_bot` 合并模式，单测覆盖覆盖/继承矩阵。
- [embedding/rerank 占位被误解为已生效] → 无实现时解析返回 disabled 语义，状态面板标注「未启用」。

## Migration Plan

1. 加 `model_roles` 结构 + 解析器；默认全空 → 全部走回退链 = 现有行为。
2. 后台任务（提取/摘要）改调解析器（回退 background→executor）。
3. UI 暴露 3 个角色；用户按需绑定。
4. P1/P2 合入后把 embedding/rerank 接到解析器。
5. 回滚：清空 `model_roles` 即回到 executor/background 行为。

## Open Questions

- 是否保留 `background_model` 字段长期共存，还是迁移后弃用（倾向保留一段时间，标记 deprecated）？
- embedding/rerank 在 `model_roles` 里用 `{provider,model}` 还是直接复用 P1/P2 既有字段名（需与 P1/P2 命名对齐，避免重复）。
