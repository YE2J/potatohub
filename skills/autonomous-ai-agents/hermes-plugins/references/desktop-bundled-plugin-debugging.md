# Debugging Hermes Desktop Bundled Plugins (hermes-bots / BOTS tab)

Case study: 2026-08-23, Hermes desktop v0.17.0. After `hermes update`, the BOTS tab
in the left sidebar either rendered an EMPTY roster or the whole tab vanished.

## Architecture facts (verified from source + disk)

- Bundled desktop plugins live at `apps/desktop/src/plugins/<name>/plugin.js`
  and auto-register via vite glob (`src/contrib/plugins.ts`). `hermes-bots`
  (Bot Mode) ships in-tree and is ON by default.
- The desktop app does NOT load `apps/desktop/dist/` directly at runtime.
  The running app loads `apps/desktop/release/mac-arm64/Hermes.app/Contents/
  Resources/app.asar` (see renderer `--app-path`). **Rebuilding requires
  `npm run pack`** (vite build + electron-builder), not just `npm run build`.
- hermes-bots registers a `panes` contribution `{ id: 'pane', title: 'Bots',
  dock: { pane: 'sessions', pos: 'center', enforce: true } }` → this is what
  creates the SESSIONS | BOTS tab strip in the left sidebar.
- Plugin storage keys appear in the renderer's Local Storage (LevelDB under
  `~/Library/Application Support/Hermes/Local Storage/leveldb/`), e.g.
  `activity-toasts`, `group-chats`, `bot-meta` / `bot-meta-v2`.

## Diagnostic ladder (BOTS empty / tab missing)

1. **Verify the backend is fine** — do not blame data. The roster data comes
   from the serve process (`profiles.list` over WS, or REST `/api/profiles`).
   Read the serve token from the process env, then hit the endpoint:
   ```bash
   ps eww -p $(pgrep -f "hermes_cli.main serve" | head -1) | tr ' ' '\n' | grep HERMES_DASHBOARD_SESSION_TOKEN
   curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:PORT/api/profiles
   ```
   If all profiles return, the bug is frontend/plugin-side, not data.
2. **Check the plugin actually loaded** — look for its storage keys in
   renderer Local Storage LevelDB:
   ```bash
   strings ~/Library/Application\ Support/Hermes/Local\ Storage/leveldb/*.ldb | grep -i "activity-toasts\|group-chats"
   ```
   Presence (with recent mtime on the .ldb) proves the plugin ran this session.
3. **Inspect the built bundle for undefined references.** This is the key
   signal: a minifier (esbuild/rolldown) renames local functions, so a call to
   an **undefined** free variable keeps its literal name in the bundle, while
   a defined function disappears (renamed). So:
   - Buggy build: `activeBotRoute` appears in `dist/assets/index-*.js` as a
     call (`await activeBotRoute()`) with NO `function activeBotRoute` /
     `const activeBotRoute` anywhere → runtime `ReferenceError`.
   - Fixed build: the name appears 0 times because it is now a real local
     function that got minified.
   ```bash
   grep -c "activeBotRoute" apps/desktop/dist/assets/index-*.js   # buggy: >0; fixed: 0
   ```
   Root cause example: hermes-bots' `useRoster()` queryFn called
   `activeBotRoute()` which was never defined → roster query threw →
   BotsPane fell back to empty `$lastRoster` → blank tab with no error banner.
4. **Check renderer console** for uncaught errors in `~/.hermes/logs/desktop.log`
   (lines like `[renderer console] Uncaught Error: ...`). Note: only some
   renderer errors land there; the bundle-inspection method (3) is the
   authoritative check.

## The rollback pitfall (IMPORTANT)

Fixing by checking out an OLD version of the plugin source is dangerous:
`hermes-bots/plugin.js` from 8-18 called `host.activeSessionId` and
`host.openExternal`, which the CURRENT SDK (`apps/desktop/src/sdk/index.ts`)
no longer exposes (`activeSessionId` moved under `host.state`, `openExternal`
removed). A stale plugin file + current SDK → registration throws → **the
whole BOTS tab vanishes** (worse than the original empty-roster bug).

Correct fix pattern: **keep the NEWEST plugin.js** (matches current SDK) and
patch in ONLY the missing symbol. E.g. add an `activeBotRoute()` that mirrors
the route shape `botConnectionRoute()` returns:
```js
function activeBotRoute() {
  const profile = String(host.state.profile?.get?.() || 'default').trim() || 'default'
  const connectionId = String(host.state.connectionId?.get?.() || host.activeConnectionId?.() || 'local').trim()
  if (!connectionId) return null
  return { connectionId, mode: connectionId === 'local' ? 'local' : 'remote', profile, targetProfile: profile }
}
```
Then re-verify: `node --check plugin.js` (syntax), rebuild, and confirm the
symbol count in the new bundle dropped to 0.

## Rebuild + verify cycle

```bash
cd ~/.hermes/hermes-agent/apps/desktop
npm install --no-audit --no-fund          # if node_modules is incomplete
npm run pack                              # = build + electron-builder; writes release/mac-arm64/...
# Verify the packed asar actually contains the fix:
node -e "
const asar = require('@electron/asar');
const p = 'release/mac-arm64/Hermes.app/Contents/Resources/app.asar';
const files = asar.listPackage(p);
const idx = files.filter(f=>f.includes('/dist/assets/index-') && f.endsWith('.js'))[0];
const src = asar.extractFile(p, idx.replace(/^\//,'')).toString('utf8');
console.log('activeBotRoute occurrences:', (src.match(/activeBotRoute/g)||[]).length); // expect 0 when fixed
"
```
User must fully quit the app (Cmd+Q) and relaunch — dock enforcement
(`enforce: true`) re-adopts the Bots pane into the sessions strip on every
boot, so a plain refresh may not pick up a rebuilt asar.

## Git notes

The install at `~/.hermes/hermes-agent` may be a **shallow clone** with
rewritten history (Aug 2026). Verify ancestry before any whole-repo rollback:
`git merge-base --is-ancestor <commit> HEAD`. If NO, do NOT `git checkout
<commit>` (detaches from main / may not have the objects) — restore single
files via `git checkout <commit> -- <path>` when the blob exists, or patch
forward as above.
