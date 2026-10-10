## 1. Backend list APIs

- [x] 1.1 Add `GET /api/bots/{bot_id}/memory/l0?session_id=&limit=&offset=` in `main.py`.
- [x] 1.2 Implement L0 list helper using `list_recent_evidence` / glob with pagination and preview text.
- [x] 1.3 Add `GET /api/bots/{bot_id}/memory/l2?limit=` using `list_session_summaries`.
- [x] 1.4 Add `GET /api/bots/{bot_id}/memory/search?q=&limit=` using `search_memory`.
- [x] 1.5 Return 404 for missing Bot; empty arrays for Bots with no data.
- [x] 1.6 Optionally add `limit`/`offset` to existing L1 list endpoint.

## 2. API tests

- [x] 2.1 Add smoke tests for L0/L2/search endpoints (empty bot, populated bot).
- [x] 2.2 Extend `test_api_smoke.py` with memory list routes when server running.

## 3. Memory browser UI shell

- [x] 3.1 Add `#memory-browser-modal` to `index.html` with header, four tabs, search input, list area.
- [x] 3.2 Add `state.memoryBrowser` and `openMemoryBrowser` / `closeMemoryBrowser` in `app.js`.
- [x] 3.3 Style modal, tabs, type badges, empty states in `style.css` (reuse brain-status visual language).

## 4. Tab rendering

- [x] 4.1 Implement `loadMemoryTab(tab)` fetching the correct API per tab.
- [x] 4.2 L0: group by session, show preview snippets.
- [x] 4.3 L1: type badge + content + session + delete button.
- [x] 4.4 L2: title + summary excerpt + click to switch session.
- [x] 4.5 L3: read-only Markdown or preformatted profile text.

## 5. Search and delete

- [x] 5.1 Wire search input to `/memory/search` with debounce.
- [x] 5.2 Implement L1 delete with confirm dialog; call existing DELETE API.
- [x] 5.3 After delete, reload L1 tab and `loadBrainStatus({ silent: true })`.

## 6. Status panel integration

- [x] 6.1 Make L0/L1/L2 counts clickable in `renderBrainStatusModal`.
- [x] 6.2 Add「查看记忆库」link opening browser on L1 tab.
- [x] 6.3 Pass `state.selectedBotId` and optional `sessionFilter` into browser.

## 7. UX polish

- [x] 7.1 Empty states per tab with actionable hints.
- [x] 7.2 Loading and error toasts for failed API calls.
- [x] 7.3 Ensure memory browser scrolls independently (reuse scroll patterns from brain-status modal).
- [x] 7.4 Mobile-friendly tab layout.

## 8. Manual acceptance

- [ ] 8.1 Open status panel → click L1 count → see atom list.
- [ ] 8.2 Send messages → L0/L1 populate → browser reflects new items.
- [ ] 8.3 Delete L1 atom → count in status panel decreases.
- [ ] 8.4 L2 item click → switches to that session.
- [ ] 8.5 Search returns relevant L1 snippets.
