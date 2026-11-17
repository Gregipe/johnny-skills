# Playbook Save Persistence — Debugging Session (May 30, 2026)

## Problem

User reported that follow-up rule text inputs ("then" field) don't persist after clicking "Save Changes" in the Conversational Playbook modal. Dropdown changes (if/time) saved fine, but typed text in the NLP input reverted on reopen.

## Debugging Process

### Step 1: Check if save functions exist

```javascript
typeof savePlaybook  // → "function" — OK
typeof savePlaybookData  // → "function" — OK
typeof updatePlaybookRule  // → "function" — OK
```

### Step 2: Test save via console (bypasses UI)

```javascript
var rules = getRules();
rules[0].time = 48;
savePlaybook();
JSON.parse(localStorage.getItem('ara_cadence_data')).cold.playbook.engaged.rules[0].time
// → 48 — save works from console
```

### Step 3: Test save via actual button click

Clicked the "Save Changes" button physically in the browser. Then checked localStorage:

```javascript
JSON.parse(localStorage.getItem('ara_cadence_data')).cold.playbook
// → undefined — save did NOT happen via button click!
```

### Step 4: Add debug logging

Added `window.onerror` handler and `[PB]` console logs to save functions. Reloaded page. Console showed:

```
GLOBAL_ERR: Uncaught ReferenceError: doLoadTemplate is not defined
```

This was the hidden bug — line 2128 reads `var _origLoad = doLoadTemplate` but `doLoadTemplate` was never declared.

### Step 5: Fix the ReferenceError

Changed:
```javascript
var _origLoad = doLoadTemplate;
doLoadTemplate = function(id) { ... };
```
To:
```javascript
var doLoadTemplate = window.doLoadTemplate || function(){};
var _origLoad = doLoadTemplate;
doLoadTemplate = function(id) { ... };
```

### Step 6: Re-test save after fix

Save worked from console but still not after UI click. Added `savePlaybook()` to read all DOM inputs before saving:

```javascript
function savePlaybook() {
  var inputs = document.querySelectorAll('#playbookWorkspace input[data-field="then"]');
  inputs.forEach(function(inp) {
    var idx = parseInt(inp.dataset.ridx);
    var rules = getRules();
    if (rules[idx]) rules[idx].then = inp.value;
  });
  // ... also sync selects
  savePlaybookData();
  showToast('Playbook saved');
}
```

### Step 7: Verify end-to-end

```javascript
// Add rule, type text, save (NO change event fired)
var newInput = document.querySelectorAll('#playbookWorkspace input[data-field="then"]');
newInput[newInput.length - 1].value = 'not interested';
document.querySelector('button[onclick="savePlaybook()"]').click();

// Close and reopen
closePlaybook();
openPlaybook();

// Check persisted
JSON.parse(localStorage.getItem('ara_cadence_data')).cold.playbook.engaged.rules[2].then
// → "not interested" ✅
```

## Key Learnings

1. **Always add `window.onerror` first** — hidden ReferenceErrors in initialization code don't show in the browser_snapshot console output but are the #1 cause of "save doesn't work" bugs.
2. **Don't trust `onchange` for text inputs** — `<input type="text">` only fires `change` on blur. `<select>` fires on selection. These are fundamentally different timing models. Always read DOM values at save time.
3. **Server restart verification** — The ARA server imports `CADENCE_HTML` at startup via `from cadence_template import CADENCE_HTML`. After editing the template, you must restart the server AND hard-refresh the browser (Cmd+Shift+R). A regular refresh may serve cached HTML. To verify the right code is served: `curl -s http://localhost:8766/cadence | grep -c "your-marker"`.
4. **Process management** — Multiple stale server processes can accumulate. Use `lsof -i :8766 | grep LISTEN` to find the actual PID, then `kill -9 <PID>` before restarting. `pkill -f "venv/bin/python server.py"` may miss processes with slightly different command lines.
5. **browser_console tool quirks** — When the session tab is navigated away (e.g., by `location.reload()`), the browser_console stops reporting messages and `localStorage` becomes inaccessible (about:blank). Always navigate back to the target page.
