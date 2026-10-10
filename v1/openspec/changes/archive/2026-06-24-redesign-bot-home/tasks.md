## 1. Backend support

- [x] 1.1 Add a Bot order persistence path so reordered launcher cards are saved and restored from `config.json`.
- [x] 1.2 Add or extend Bot config APIs to support updating `constraints` alongside existing Soul and Bot fields.
- [x] 1.3 Ensure Bot readiness data returned to the frontend is sufficient to show bound-provider vs unconfigured-brain state.

## 2. Launcher home UI

- [x] 2.1 Replace the current default Bot/session sidebar-first entry with a Bot launcher home screen in `meclaw2/web/index.html`.
- [x] 2.2 Implement Bot grid rendering in `meclaw2/web/app.js`, including Bot tiles, the fixed trailing `+` tile, and enter/edit/delete actions.
- [x] 2.3 Add launcher arrange mode with jiggle animation state, drag-and-drop reordering, and persisted exit/save behavior.
- [x] 2.4 Add a clear transition between launcher home and Bot-scoped chat workspace, including a return-to-launcher action.

## 3. Bot editor and settings flow

- [x] 3.1 Build a Bot editor modal that groups name, avatar, provider binding, model override, temperature, and max token fields.
- [x] 3.2 Add Soul and constraints editing to the Bot editor modal and wire saves to the backend.
- [x] 3.3 Surface provider status and missing-provider guidance inside the Bot editor without duplicating provider CRUD there.
- [x] 3.4 Simplify settings navigation so provider management remains available while Bot management is no longer the primary path.

## 4. Polish and verification

- [x] 4.1 Update styles for the launcher grid, card actions, arrange mode, and modal layout so the 2.0 UI matches the new home-first interaction model.
- [x] 4.2 Verify key flows manually: add provider, create Bot, bind provider, edit Soul/constraints, reorder Bots, delete Bot, enter chat, and return to launcher.
- [x] 4.3 Refresh any 2.0 documentation or smoke-test notes that still describe the old sidebar-first Bot management flow.
