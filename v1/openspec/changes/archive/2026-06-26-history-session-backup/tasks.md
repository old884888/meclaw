## 1. Backup Rotation

- [x] 1.1 Extend `write_json_atomic` or add `write_json_with_rotation` supporting N-generation suffix rotation (`.bak1`, `.bak2`, …)
- [x] 1.2 Enable rotation in `save_messages()` (replace `backup=False`)
- [x] 1.3 Enable rotation in `save_sessions_index()` when `backup=True` or always-on for index

## 2. Configuration

- [x] 2.1 Add `history_backup_generations` to config schema (default 3, clamp 1–10)
- [x] 2.2 Wire config into history store save paths

## 3. Operator Visibility

- [x] 3.1 Include backup generation count in `/api/system/data-info`
- [x] 3.2 Document manual restore steps in change notes or README snippet

## 4. Tests

- [x] 4.1 Unit test: three consecutive saves produce `.bak1` and `.bak2` with expected content
- [x] 4.2 Unit test: rotation drops oldest when limit exceeded
- [x] 4.3 Verify data export includes backup files (if export walks history dir)
