## Context

Current heuristic L1 extraction copies user message text up to 500 chars with type inferred by keyword regex. L3 groups by 8 topic regex buckets and shows newest-first bullets with `[当前]/[曾经]`. PersonaMem evolution questions require ordered A→B→C chains and stated reasons — flat bullets lose temporal and causal structure.

Benchmark baseline (official 50, memory mode, heuristic):
- `track_full_preference_evolution`: 22%
- `recalling_the_reasons_behind_previous_updates`: 60%
- `provide_preference_aligned_recommendations`: 86%

## Goals / Non-Goals

**Goals:**
- Make preference evolution inspectable in L3 and retrievable as a chain in one injection block.
- Improve PersonaMem evolution/reason accuracy without requiring LLM extraction by default.
- Backward compatible with existing L1 files missing new fields.

**Non-Goals:**
- Full LLM-based L1 rewrite (optional benchmark comparison only).
- Learner brain integration.
- Cross-bot preference merging.

## Decisions

### Decision: L1 metadata extensions (schema_version 2)

New frontmatter fields on write:
- `topic_key` (string, normalized slug)
- `polarity` (`positive` | `negative` | `switch`)
- `seq` (monotonic int per bot, or nanosecond timestamp)
- `reason` (optional string, extracted from 因为/由于/since/because clauses)

Heuristic `topic_key`: expand keyword→slug map (drink, writing, travel, …); fallback `misc_{hash_prefix}`.

Heuristic `polarity`: switch hints override positive/negative detection.

**Alternative considered:** Separate L1.5 graph store. Rejected — keep atoms as source of truth.

### Decision: L3 timeline renderer replaces flat `[当前]/[曾经]` for preferences

For each `topic_key` group with >1 preference atom, render:

```text
**{topic_label}（演变）**
① {date} {value}
② {date} → {new_value}  原因：{reason}
→ 当前：{latest_value}
```

Single-atom topics keep simple bullet.

### Decision: Topic-chain recall expansion

When hybrid/FTS hits an L1 atom with `topic_key`:
1. Fetch all non-deleted atoms sharing that key (same bot scope).
2. Sort by `seq` ascending.
3. Inject as one grouped block before individual top-k snippets.

Budget: chain block counted first; may reduce unrelated atom count.

### Decision: Benchmark gate before claiming success

Require official 50+ run comparing:
- heuristic + chain recall (this change)
- optional `--extract llm` on same limit

Target: evolution accuracy >40% on 50 questions (directional, not SOTA claim).

## Risks / Trade-offs

- [Risk] Wrong `topic_key` merges unrelated prefs. → Conservative map; prefer `misc_*` over wrong merge.
- [Risk] Chain blocks consume token budget. → Cap chain length (e.g. last 5 events per topic).
- [Risk] seq collision on legacy atoms. → Backfill seq from `created_at` + file mtime on read.

## Migration Plan

1. Deploy extractor + store changes (new atoms get fields).
2. Deploy L3 aggregator timeline format.
3. Deploy retrieval chain expansion.
4. Optional one-time `rebuild_bot_index` + force L3 refresh per bot.

No automatic rewrite of old L1 file bodies.

## Open Questions

- Minimum topic map size for v1? Start with ~15 English/Chinese keyword groups aligned to PersonaMem domains (food, travel, writing, music, health).
