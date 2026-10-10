## 1. Placeholder Bubble

- [x] 1.1 Add `ensureWaitingBubble()` in `app.js` that creates assistant wrap with loading dots and status label on send
- [x] 1.2 Call `ensureWaitingBubble()` from `sendMessage()` immediately after `setGenerating(true)`
- [x] 1.3 Refactor `ensureStreamingBubble()` to upgrade existing waiting bubble instead of always creating a new row

## 2. Generation State Machine

- [x] 2.1 Add `generationPhase` state (`waiting` | `retrieving` | `streaming`)
- [x] 2.2 Update status label on `brain_trace` event to 「正在检索记忆…」
- [x] 2.3 Start 8s timeout timer on send; update label to 「仍在等待模型响应…」 if no token yet
- [x] 2.4 Clear timeout and reset phase on `done` / `stopped` / `error`

## 3. Streaming Transition

- [x] 3.1 On first `token`, remove waiting UI and attach `.msg-body` + cursor in same wrap
- [x] 3.2 Ensure error path removes orphan placeholder when no tokens received
- [x] 3.3 Verify stop-generation clears placeholder cleanly

## 4. Styles

- [x] 4.1 Add CSS for `.msg-waiting`, `.msg-waiting-dots`, and status label in `index.html` or existing stylesheet
- [x] 4.2 Match existing assistant bubble spacing and dark/light theme tokens

## 5. Validation

- [x] 5.1 Manual test: send message with memory enabled — placeholder → retrieving → streaming
- [x] 5.2 Manual test: send with brain_trace disabled — placeholder → streaming only
- [x] 5.3 Manual test: API error before token — no duplicate assistant rows
