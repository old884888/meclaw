## Context

The Memory brain spec already reserves L3 as a compressed long-term persona input, but current behavior is shallow compared to PersonaMem-style personalization tasks. L1 atoms capture individual facts/preferences, and L2 summaries capture session progress, but the system needs a stable L3 profile that summarizes durable user preferences and constraints for routine injection.

This change builds on hybrid recall but is separable: hybrid recall improves finding individual records, while L3 profile improves always-available personalization context.

## Goals / Non-Goals

**Goals:**

- Generate and maintain a bot-scoped L3 profile from L1/L2 memory.
- Store the profile as human-readable local data under the bot memory directory.
- Inject a bounded excerpt into chat/persona context without modifying `soul.md`.
- Handle preference evolution by favoring newer active preferences while retaining evidence.

**Non-Goals:**

- Full learner/skill generation.
- Automatic edits to Soul files.
- Remote embedding dependency.
- Perfect conflict resolution for all domains in the first pass.

## Decisions

### Decision: Store L3 profile as Markdown plus structured metadata

Use a readable `memory/l3/profile.md` (or existing L3 path if present) with sections such as preferences, constraints, style, recurring projects, and open todos. Keep source ids or session references in metadata/comments or sidecar JSON where needed for traceability.

Alternative considered: SQLite-only profile. Rejected because L3 should be inspectable and manually understandable.

### Decision: Start with heuristic aggregation, allow optional LLM refresh later

The first pass should aggregate L1 atoms by type/topic and recency. Optional LLM-based rewrite can be added behind existing background model configuration, but the system should produce a useful profile without API calls.

### Decision: Inject L3 before volatile L1 recall

For personalization, a compact L3 profile is often more useful than scattered L1 snippets. `before_chat()` or Persona brain integration should include L3 within `persona_token_budget`/`memory_token_budget`, then add query-specific L1 recall when available.

### Decision: Preference evolution uses active/latest markers

When conflicting preferences exist, L3 should favor the newer statement while preserving older evidence in L1/L0. It should not delete historical memory unless the user explicitly requests deletion.

## Risks / Trade-offs

- [Risk] Incorrect profile summary can bias all future replies. → Mitigation: keep profile human-readable, trace sources, and limit automatic confidence.
- [Risk] L3 grows stale. → Mitigation: refresh on configured intervals and expose last-updated metadata.
- [Risk] Over-injection increases token use. → Mitigation: enforce `persona_token_budget` and compact profile excerpts.
- [Risk] Heuristic aggregation misses implicit preferences. → Mitigation: allow optional LLM refresh later and measure with PersonaMem.

## Migration Plan

1. Reuse existing bot memory directories and create L3 files lazily.
2. Build profile from existing L1/L2 records when missing.
3. Inject only if file exists and memory/persona settings allow it.
4. Rollback by disabling L3 injection or removing generated profile files; L1/L0 evidence remains intact.
