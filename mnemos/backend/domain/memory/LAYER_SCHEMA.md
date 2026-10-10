# L2/L3 frontmatter schema (reserved, not auto-generated in Phase 1)

## L2 scenario example

```yaml
schema_version: 1
id: l2_xxx
title: 主题块标题
topic: 检索技术
source_l1_ids: [note_aaa, note_bbb]
summary: 若干 L1 原子事实的聚合摘要
layer: L2
created_at: 2026-06-16T20:00:00
```

## L3 profile example

```yaml
schema_version: 1
id: l3_xxx
profile_type: user_profile | knowledge_profile
source_l2_ids: [l2_xxx]
summary: 长期偏好或知识画像
layer: L3
updated_at: 2026-06-16T20:00:00
```

Trace chain: L3 -> L2 -> L1 -> L0
