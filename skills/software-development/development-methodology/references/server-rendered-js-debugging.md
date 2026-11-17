# Server-Rendered JS Debugging Patterns

## Case 1: FastAPI Route Shadowing

**Symptom:** `GET /api/actions` returns `[]` (empty array), but:
- `GET /api/actions/stats` returns `{"upcoming": 1, ...}`
- Direct SQL query `SELECT * FROM scheduled_actions` returns 1 row
- Python script querying the same model returns the record

**Root cause:** An OLDER `@app.get("/api/actions")` (from the original `ActionItem` system) was registered BEFORE the new `@app.get("/api/actions")` (from `ScheduledAction`). FastAPI routes are matched in registration order — the old endpoint wins and queries a different table.

**Debug command:**
```bash
grep -n '@app.*/api/actions' server.py
```

**Fix:** Remove the old endpoint (or rename to a different path).

## Case 2: Python String Escaping Breaking Inline JavaScript

**Symptom:** All JS functions undefined (`typeof showPage === "undefined"`), sidebar nav items don't work, no console errors reported. The entire inline `<script>` block is silently failing.

**Root cause:** A syntax error in the JavaScript kills the entire 130KB+ inline script block. No functions survive — not just the broken one.

**Debug flow:**
1. Check if any JS functions exist: `typeof showPage` → `"undefined"` means the whole block failed
2. Validate syntax: `curl -s <url> | extract script > /tmp/check.js && node --check /tmp/check.js`
3. The error pinpoints the exact line

**The Python escaping trap:**

```python
# WRONG — \' in Python single-quoted string produces bare ':
cancelBtn = '<span class="ac-action" onclick="cancelAction(\'' + a.id + '\')">Cancel</span>'
# Renders: ...onclick="cancelAction('' + a.id + '')"  ← '' is empty string in JS
# This works by accident but is fragile — same pattern with text (Ava's) breaks

# CORRECT — use \\x27 (double backslash so Python outputs \x27 for JS):
cancelBtn = '<span class="ac-action" onclick="cancelAction(\\x27' + a.id + '\\x27)">Cancel</span>'
# Renders: ...onclick="cancelAction(\x27abc123\x27)" → JS decodes \x27 as ' ✓
```

**Why `\'` behaves differently from what you expect:**
- Inside ANY Python string (`'...'`, `"..."`, `"""..."""`): `\'` is a recognized escape → produces just `'` (backslash consumed)
- To preserve the backslash for JS, use `\\'` (two backslashes) or `\\x27` which is unambiguous at every layer

**Pattern to search for when debugging:**
```bash
grep -rn "onclick.*cancelAction" dashboard_template.py
# Look for '' + a.id + '' patterns (two empty strings) vs proper quoted args
```

## Case 3: HTML `\"` Contamination from JS String Escaping

When building HTML inside JS strings, `\"` is an escaped double quote (valid in JS `"..."`). But in the **rendered HTML**, `\"` is NOT an HTML escape — `\` is just a literal backslash character.

**Wrong:** JS string produces HTML with `\"` — browsers interpret this as a literal backslash before the quote.
**Right:** Use the correct mix of `'` and `"` so both JS strings and HTML attributes are valid simultaneously:
- JS double-quoted string: `"..."` — use `\"` for HTML attr quotes (escaped in JS), `'` for JS string args inside onclick (literal)
- JS single-quoted string: `'...'` — use `"` for HTML attr quotes (literal), `\'` for JS string args inside onclick (escaped)

## Case 4: Function References Variable from Calling Scope That Doesn't Exist

**Symptom:** A button click calls `someFunction()` which fails with `ReferenceError: X is not defined`. The function `X` IS defined inside another function, but the callee can't see it.

**Root cause:** A helper function (like `gvPbVal`) was written assuming `pb` (or another variable) would be in scope. It was originally tested only from within `applyPbData()` where `pb` was a local variable. When called from `collectPbParts()` (which also defines `pb` locally), JavaScript didn't use the calling function's `pb` — because `gvPbVal` is a **separate function declaration**, not a closure. Each function has its own scope chain.

**Debug flow:**
1. Navigate to the page, open the builder/component
2. Click the broken button (e.g., "Save Changes")
3. Check console: `try { functionName(); } catch(e) { e.message; e.stack; }`
4. Read the stack trace — find which function and line number failed
5. Read the function definition — does it reference a variable that isn't declared locally?
6. Fix: add `var pb = document.getElementById('pbOverlay');` inside the helper function

**The JS scope rule:**
```javascript
var x = 'global';
function outer() {
  var x = 'outer';
  function inner() {
    console.log(x); // 'outer' — closure, inner is defined INSIDE outer
  }
  inner();
}

function standalone() {
  console.log(x); // 'global' — NOT 'outer', because standalone is NOT inside outer()
}

outer();
standalone();
```

**Fix pattern:** Every standalone helper function that needs `pb` must declare it:
```javascript
function gvPbVal(id) {
  var pb = document.getElementById('pbOverlay');
  if (!pb) return '';
  var el = pb.querySelector('#' + id);
  return el ? el.value : '';
}
```

**Prevention:** When extracting a helper function from within another function, check every variable reference in the helper. If any variable was a parameter or local of the original function, it must either be passed as an argument or looked up anew.

**Greppable pattern in ARA:**
```bash
grep -n 'function gvPbVal\|function setPbVal\|function collectPbParts' prompt_builder_template.py
# Check each for standalone pb reference
```

## Case 5: Silent ReferenceError from Undeclared Variable in Assignment Pattern

**Symptom:** Most JS functions work (`typeof savePlaybook === 'function'`), but the save chain silently fails. No visible error in the browser console — `browser_console` shows empty-string `js_errors` entries with no message or stack. The user reports "save doesn't work" even though the code compiles fine.

**Root cause:** An inline script contains a pattern like:
```javascript
var _origLoad = doLoadTemplate;           // ← REFERENCE: doLoadTemplate NOT declared
doLoadTemplate = function(id) { ... };    // ← ASSIGNMENT: creates global in non-strict mode
```
`doLoadTemplate` is assigned to (creating an implicit global in non-strict mode) but **never declared with `var`/`let`/`const` or `function`**. When the code tries to READ `doLoadTemplate` (on the `var _origLoad = ...` line), it throws `ReferenceError: doLoadTemplate is not defined`. Because this is in non-strict mode, the error stops the current block but doesn't kill the entire script — subsequent functions ARE defined. The code runs but with corrupted state.

**Why this is hard to spot:**
- `new Function(scriptText)` passes syntax validation (valid JS, just a runtime error)
- `browser_console()` returns empty-string exceptions (`"js_errors": [{"message": "", "source": "exception"}]`)
- Most functions still exist because the ReferenceError only stops execution at that point
- If the error is at the module/global level (not inside a function), it can corrupt the init sequence

**Debug flow:**

### Step 1 — Catch the Silent Error
```javascript
// Add to the page source (NOT browser console — survives reload):
// Place at top of <script> block:
window.onerror = function(m, f, l, c, err) {
  console.log('GLOBAL_ERR:', m, f, l, c, err ? err.stack : '');
};
window.addEventListener('unhandledrejection', function(e) {
  console.log('PROMISE_REJ:', e.reason);
});
```

### Step 2 — Inject Console Markers via Python Template
When debugging inline JS behavior across function boundaries, embed `console.log('[TAG]' + ...)` markers directly in the Python template file that generates the HTML. Patch the `.py` file, restart the server, and reload:

```python
# In cadence_template.py (or similar):
def getPlaybookData():
  if (playbookData) { console.log('[PB] cache hit'); return playbookData; }
  var t = getTemplate();
  console.log('[PB] getPlaybookData: t.playbook=' + (t && t.playbook ? 'exists' : 'null/undefined'));
  if (!t.playbook) { console.log('[PB] creating fresh playbook object'); t.playbook = {}; }
  ...
```

Pattern for markers:
- `'[AREA] event description: [key values]'` — use a short tag per area (`[PB]`, `[SAVE]`, `[LOAD]`)
- Include the values that matter (object keys, lengths, existence checks)
- Add a VERIFY step after any `saveData()`/`setItem()` call to confirm persistence

### Step 3 — Confirm the Pattern
```javascript
// Check for the assignment pattern:
// Is there a line like: var X = someVar; followed by someVar = function(){...}?
// If someVar was never declared, this throws ReferenceError on the read.

// Quick check — does the variable exist on window?
typeof window.doLoadTemplate  // "undefined" → never declared
```

### Step 4 — The Fix
Add a proper declaration before the read:
```javascript
// BEFORE (broken):
var _origLoad = doLoadTemplate;
doLoadTemplate = function(id) { ... };

// AFTER (fixed):
var doLoadTemplate = window.doLoadTemplate || function(){};
var _origLoad = doLoadTemplate;
doLoadTemplate = function(id) {
  if (_origLoad) _origLoad(id);
  ...
};
```

The `window.doLoadTemplate || function(){}` pattern ensures:
- `doLoadTemplate` is properly declared in scope (no ReferenceError)
- If someone else defined it earlier (e.g., another script tag), the existing implementation is preserved
- If not, a no-op placeholder is used, and `_origLoad` will be the no-op (which `if (_origLoad)` skips)

### Prevention
When writing inline JS patterns that stub/shim/wrap existing functions:
1. Every variable read on the right side of `=` must have a corresponding `var`/`function`/`let`/`const` declaration somewhere
2. The assignment-then-read pattern (`var _orig = X; X = function(){...}`) requires `X` to be defined before the read
3. Search for this pattern in the codebase:
   ```bash
   grep -n 'var _orig\w* = \|var __orig' *.py
   # Look for variables that are referenced but never declared with var/function
   ```
