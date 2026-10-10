## Why

MeClaw2 persists each chat session as a single JSON file rewritten on every message append. There is no rolling backup (`backup=False`), so a corrupted write, sync conflict, or accidental edit can destroy an entire long conversation. As sessions grow, full-file rewrites also increase IO cost and failure blast radius.

## What Changes

- Enable rolling backup on session message writes (keep last N versions per session file).
- Add optional backup rotation policy in config (count, suffix pattern).
- Expose backup file locations in system data-info for operator visibility.
- Document recovery procedure (restore from `.bak`).

## Capabilities

### New Capabilities

- `meclaw2-history-persistence`: Session file durability, rolling backups, and recovery semantics.

### Modified Capabilities

- None.

## Impact

- Affected backend:
  - `meclaw2/backend/storage/history_store.py`
  - `meclaw2/backend/storage/common.py` (`write_json_atomic` backup behavior)
  - `meclaw2/backend/main.py` (`/api/system/data-info` if extended)
- Disk usage increases slightly (N copies per active session file).
- No breaking API changes; message schema unchanged.
