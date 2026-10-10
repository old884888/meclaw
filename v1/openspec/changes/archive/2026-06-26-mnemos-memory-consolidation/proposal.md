## Why

P4 解决了写入去重、supersede 与召回加权，但缺少「巩固与遗忘」：L1/L3 会无限增长，L2 轻量摘要仍是截断占位。Hermes 资料中的约束驱动提炼（容量阈值 → 强制合并）正是海马体模型里缺的那一半。本提案为记忆层增加主动归并、压缩与归档，控制长期噪声。

## What Changes

- 容量阈值：L3 profile、topic 链长度、L2 summary 超限时触发 consolidation job
- 动作类型：`merge`（近似重复）、`compress`（长链摘要节点）、`archive`（低 importance + 低 hit + 旧 recency）
- `pin` 规则：constraint 类型、高 importance 永不 archive
- 后台异步 job，不阻塞聊天
- 配置：`memory_consolidation_enabled`, 各层 capacity 阈值

## Capabilities

### New Capabilities

- `mnemos-memory-consolidation`: Capacity-driven merge, compress, and archive jobs for L1/L2/L3.

### Modified Capabilities

- `mnemos-memory-brain`: SHALL schedule consolidation when capacity thresholds are exceeded.

## Impact

- 后端：新 `consolidation/` 模块、`memory_brain.py`、`profile_aggregator.py`、`tier3_summarizer.py`
- 使用 summary 角色做 LLM 归并（可选）
- 验证：长会话模拟噪声率；PersonaMem 长上下文 replay（可选）
