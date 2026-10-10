## Context

`history_store.save_messages()` calls `write_json_atomic(..., backup=False)`. The atomic rename prevents half-written files but leaves no history if the new content is bad or the file is corrupted externally. Long sessions rewrite the entire JSON array each turn.

## Goals / Non-Goals

**Goals:**
- Protect against single-write corruption with minimal operator effort.
- Keep implementation local-first; no external backup service.
- Default-on rolling backup with sensible defaults (e.g. 3 generations).

**Non-Goals:**
- JSONL append-only migration (future change).
- Session archival / compaction (future change).
- UI restore wizard (document manual restore only).

## Decisions

### Decision: Rotate backups on each successful write

Before atomic replace, if target exists, rotate:
`session.json` → `.bak1` → `.bak2` → `.bak3` (drop oldest).

Implement in `write_json_atomic` when `backup=True` or dedicated `save_messages` wrapper.

**Alternative considered:** Timestamped backups. Rejected for MVP — unbounded disk growth.

### Decision: Default backup count = 3

Configurable via `history_backup_generations` in config (default 3, min 1, max 10).

### Decision: sessions.json index gets backup too

Apply same rotation to `sessions.json` since it is also rewritten atomically without backup today.

## Risks / Trade-offs

- [Risk] Disk usage on very chatty installs. → Cap at 10 generations; only session files touched on write.
- [Risk] Backup contains pre-edit state only — user message already visible in UI if crash mid-write. → Atomic write still primary guarantee.

## Migration Plan

Enable on next deploy. Existing sessions get first backup on next message write. No migration script required.

## Open Questions

- Should export zip include `.bak` files? Default: yes, include in data export for disaster recovery.
