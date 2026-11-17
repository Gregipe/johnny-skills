# Frontend Data Persistence Debugging

**Pattern:** User saves data via UI → confirmation shown ("✓ Saved") → page refresh → data reverts to previous/default state.

This is distinct from an API failure — the save endpoint returns success. The bug is in the in-memory→localStorage→page-load chain.

## Diagnosis Flow

### 1. Is the Save Chain Working?

Check localStorage immediately after clicking Save:

```javascript
// In browser console, AFTER clicking Save:
var raw = localStorage.getItem('ara_cadence_data');
var data = JSON.parse(raw);
var bp = data['cold'].promptParts.brandPersonality;
console.log('Personality:', bp ? bp.personality : 'MISSING');
```

- If the data IS here → save chain works, bug is in page load
- If the data is NOT here → `saveCurrentState()` / `saveData()` not being called, or saves empty object

### 2. Verify API Layer Separately

Distinguish frontend-localStorage bug from API/DB bug:

```bash
# Direct DB check (fastest)
# For SQLite:
sqlite3 /path/to/database.db "SELECT prompt_parts FROM cadence_config WHERE template_id='cold';"

# For Python app: curl the save and check:
curl -s http://localhost:8766/api/cadence/save-draft -X POST \
  -H 'Content-Type: application/json' \
  -d '{"template_id":"cold","promptParts":{"brandPersonality":{"personality":"debug-test-123"}}}'

# Then check DB directly
```

If API/DB is fine but localStorage isn't updated, the save chain (API success handler → `saveCurrentState()` → `saveData()`) has a bug.

### 3. After Refresh — Check localStorage Raw JSON

```javascript
// After page refresh:
var raw = localStorage.getItem('ara_cadence_data');
raw.includes('promptParts')  // Does promptParts exist at all?
JSON.parse(raw)['cold'].promptParts  // Is it {} or has data?
```

**Common finding:** `promptParts` exists but is `{}` (empty object), even though it had data before refresh.

### 4. Trace the Load Chain

Identify every function that runs on page load and could modify `t.promptParts` or `TEMPLATES`:

1. **Check page init:** Search for `loadData()` — this loads localStorage into `TEMPLATES`
2. **Find the render function:** Search for `renderCurrentTemplate()` or similar — this runs at page init
3. **List ALL functions called by render:** Each one is a potential data-destroyer
4. **Check if server code is current:** Some processes run stale JS from before the patch

```javascript
// Check if loaded JS is the latest version:
var src = migrateToGlobalPromptParts.toString();
src.includes('tmpl.promptParts = {}');  // true if old buggy code is still running
```

### 5. Common Load-Chain Culprits

| Function | What It Does | Why It Destroys Data |
|----------|-------------|---------------------|
| **`migrateToGlobalPromptParts()`** | Copies `promptParts` to `globalPromptParts`, then **clears** `t.promptParts = {}` | Designed for old prompt editor. New builder reads from `t.promptParts`, not `globalPromptParts`. The clear kills the data. |
| **`prefillFromInduction()`** | Fetches prefill from API on page load, sets `globalPromptParts`, calls `saveData()` | Overwrites `globalPromptParts` (which the builder reads as fallback). Also calls `saveData()` which persists possibly-stale `TEMPLATES`. |
| **`loadPromptBuilderData()`** | Opens the builder, merges prefill into `t.promptParts` | If async prefill fetch completes AFTER the user started editing, it overwrites their changes. Check the deep-merge logic: `if (!t.promptParts[section][field])` — this only fills empty fields, but if the section itself doesn't exist in `t.promptParts` but exists in prefill, the entire section from prefill is used. |
| **`saveCurrentState()`** | Called after save, reads DOM steps/conditions, calls `saveData()` | If `getTemplate()` returns a stale reference (not the same object that was modified by save), it saves old data. Rare. |

### 6. The Server-Code Mismatch Trap

If you patched the server-side file but the behavior doesn't change:

```bash
# 1. Check if the old process is still running:
pgrep -af 'server.py' | grep -v grep
# If multiple PIDs, the oldest one might be serving stale code

# 2. Check process start vs file modification time:
ls -l /path/to/modified_file.py
ps -p <PID> -o lstart=

# If process started BEFORE file was modified, you need to restart

# 3. Confirm via browser (for inline-JS pages):
migrateToGlobalPromptParts.toString().includes('tmpl.promptParts = {}')
# If still includes old code after patching file → stale process
```

**Fix:** Kill ALL server processes, then start fresh. Shell wrappers can leave parent processes alive.

```bash
pkill -f 'python server.py'
sleep 2
ps aux | grep 'server.py' | grep -v grep  # Should be empty
# Then start fresh:
cd /project && nohup python server.py &
```

### 7. Verify the Fix

Full end-to-end test:

```javascript
// Step 1: Clear all state
localStorage.clear();

// Step 2: Load page, wait for prefill/init
// Step 3: Open the builder/form
// Step 4: Set a unique, timestamped value
document.querySelector('#pe_personality').value = 'verify-' + Date.now();

// Step 5: Click Save
document.getElementById('pbSaveBtn').click();

// Step 6: Wait for confirmation, then check localStorage
setTimeout(function() {
  var data = JSON.parse(localStorage.getItem('ara_cadence_data'));
  var bp = data['cold'].promptParts.brandPersonality;
  console.log('After save:', bp.personality);
}, 3000);  // Give async chain time to complete

// Step 7: Hard refresh the page
// Step 8: Check localStorage again
JSON.parse(localStorage.getItem('ara_cadence_data'))['cold']
  .promptParts.brandPersonality.personality;
// Should STILL be your value
```

## The "Works in Console, Not via UI" Pattern

A distinct flavor of persistence bug: the save chain works when invoked via browser console (`savePlaybook()`) but NOT when the user clicks the Save button or changes a dropdown/input.

**Root cause is almost always one of:**
1. **Browser page cache of server-rendered HTML** — User loaded page before fix was deployed, browser serves cached old HTML with broken handlers
2. **Event handler not binding** — Inline `onchange`/`onclick` not firing due to JS syntax error in the same or earlier `<script>` block
3. **Event not propagating** — Handler fires but data isn't written to the model (less common)

### Diagnosis Flow

**Step 1 — Check if JS functions exist at runtime:**

```javascript
// In browser console — if ANY core function is undefined, there's
// a syntax error that killed the entire script block
typeof savePlaybook        // should be 'function'
typeof updatePlaybookRule  // should be 'function'
typeof CHANNEL_ICONS       // first inline script variable
typeof TEMPLATES           // should be 'object'
```

If multiple are undefined → the inline `<script>` block has a syntax error. `new Function(scriptTag.textContent)` will throw.

**Step 2 — Check for runtime JS errors:**

```javascript
// Clear and check browser console for exceptions
// browser_console(clear=true) then browser_console()
// Look for js_errors array — even empty-message exceptions indicate trouble
```

Note: an empty-string exception with no stack trace still means something threw. Use `window.addEventListener('error', handler)` to capture details.

**Step 3 — Verify server serves the correct code:**

```bash
# Confirm the fix made it to the rendered HTML:
curl -s http://localhost:8766/cadence | grep -c "savePlaybook"
# > 0 means at least one reference exists in served HTML
```

If the function name appears in the HTML but is undefined in the browser → the inline script has a syntax error (see server-rendered-js-handlers skill).

**Step 4 — Isolate the save layer:**

```javascript
// Test A — Direct object mutation + save (bypass UI entirely):
var rules = getRules();
rules[0].time = 99;
savePlaybook();
JSON.parse(localStorage.getItem(STORAGE_KEY)).cold.playbook.engaged.rules[0].time
// If 99 → data layer is FINE
```

```javascript
// Test B — Dispatch change event programmatically:
var sel = document.querySelector('[data-field="time"]');
sel.value = '72';
sel.dispatchEvent(new Event('change', {bubbles: true}));
savePlaybook();
// Close and reopen playbook — check if value stuck
```

- Test A passes, Test B passes → **call this out as likely browser page cache issue**
- Test A passes, Test B fails → event handler binding is wrong (check onchange attr)
- Test A fails → data layer has a bug

### The `onchange` Race Condition (Text Inputs + Save Button)

A distinct flavor: typing in a text input → clicking Save → value doesn't stick. But calling `savePlaybook()` from the console works fine.

**Root cause:** `onchange` fires on **blur** (when the input loses focus). If the user types text and immediately clicks Save, the input never loses focus — `onchange` never fires — the data model is stale when save reads it.

**Diagnosis:**
```javascript
// Verify: after type+saving via UI, check if model has the new value:
var rules = getRules();
rules.forEach(function(r, i) {
  console.log('Rule ' + i + ': then="' + r.then + '"');
});
// If rules[i].then is still the OLD value → onchange never fired
```

**Fix 1 — `oninput` (fires on every keystroke):**
```javascript
// Add oninput alongside onchange — oninput fires on every keystroke,
// onchange fires on blur. Together they cover all interaction paths:
<input ...
  oninput="syncModel(this)"
  onchange="syncModel(this)">
```

**Fix 2 — Belt-and-suspenders: DOM-read at save time**
Even with `oninput`, edge cases exist. As a safety net, rewrite the save function to read values directly from the DOM at save time — bypasses the data model entirely for inputs:

```javascript
function savePlaybook() {
  var inputs = document.querySelectorAll('#workspace input[data-field="then"]');
  inputs.forEach(function(inp) {
    var idx = parseInt(inp.dataset.ridx);
    var rules = getRules();
    if (rules[idx]) rules[idx].then = inp.value;  // reads from DOM, not model
  });
  savePlaybookData();
}
```

This is **class-level advice** — `onchange` + immediate-save-buttons is a fundamental JS gotcha. Always use `oninput` for text fields that sync to a model when a Save button lives nearby.

### Browser Page Cache Resolution

ARA's `/cadence` (and similar) endpoints return `HTMLResponse` without `Cache-Control` headers. Browsers apply **heuristic caching**: if the response is under ~10KB or has a future `Last-Modified` after the cached copy, the browser serves the old page. A normal `Cmd+R` (or location.reload()) may NOT fetch from the server.

**Fixes (in order):**
1. **Hard refresh:** `Cmd+Shift+R` (macOS) or `Ctrl+F5` (Windows)
2. **Incognito/private window** — no cached state
3. **Clear site data:** DevTools → Application → Clear Storage → Clear site data
4. **Force no-cache server-side:** Add `Response(headers={"Cache-Control": "no-store"})` to the endpoint

### Verify Server Process Freshness

```bash
# Check if the file was modified AFTER the process started:
stat -f "%Sm" /path/to/cadence_template.py      # file mtime
ps -p <PID> -o lstart=                           # process start time

# If file mtime > process start → server loaded OLD code
# Restart the server to pick up changes

# Kill all server processes safely:
pkill -f "python server.py" 
# Or use the startup script which cleans __pycache__:
find __pycache__ -name "cadence_template*" -delete 2>/dev/null
./venv/bin/python server.py
```

### Full Resolution Flow (ARA Conversational Playbook Example)

| Step | Action | Expected | If fails |
|------|--------|----------|----------|
| 1 | `typeof savePlaybook` in browser console | `'function'` | JS syntax error in script block |
| 2 | `typeof updatePlaybookRule` | `'function'` | Same script block issue |
| 3 | Check browser console for JS errors | Empty | Fix the error in source |
| 4 | `curl -s .../cadence \| grep "savePlaybook"` | Shows function definition | Server has old code — restart |
| 5 | `stat` vs `ps lstart` for server PID | File mtime < process start | Delete __pycache__ + restart |
| 6 | Test A (direct mutation + save) | Value persists in localStorage | Data layer bug |
| 7 | Test B (dispatchEvent + save) | Value persists through close/reopen | Event handler bug |
| 8 | If all pass but UI still broken | **Browser page cache** | Hard refresh (Cmd+Shift+R) |

## Prevention

When building the save→localStorage→refresh circuit:

1. **Every function that runs on page load** is a potential data destroyer. Audit each one.
2. Use a single source of truth: if you migrate data from `t.promptParts` to `globalPromptParts`, DON'T clear the original. Both should be valid until one is explicitly deprecated.
3. Validate the full round-trip: save → check localStorage → refresh → check localStorage → open component → check value in UI.
4. Browser caching of server-rendered inline JS is rare (it's HTML, not a static asset), but **the server process might be serving stale code**. Always verify `ps -p <PID> -o lstart=` vs file mtime after patching.
5. **Distinguish stale server process from browser page cache** — hard refresh (`Cmd+Shift+R`) bypasses browser cache. If hard refresh fixes it, the server was fine all along; the browser was serving cached HTML.
