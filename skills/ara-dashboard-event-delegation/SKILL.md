---
name: ara-dashboard-event-delegation
description: Use data-action + event delegation instead of inline onclick in ARA HTML template innerHTML strings (dashboard_template.py, threads_template.py, and any future f-string JS templates). Also covers autocomplete/searchable dropdowns in modals.
---

# ARA HTML Template Event Delegation Rule
## The Problem

ARA's HTML template files (`dashboard_template.py`, `threads_template.py`, `cadence_template.py`) wrap ALL HTML + JS in a Python triple-quoted string (`DASHBOARD_HTML = """..."""`). Inside this, JavaScript builds HTML via `html += '...'` string concatenation and assigns to `innerHTML`.

Any single quote inside a JS string literal delimited by single quotes will TERMINATE the string. Adding backslash-single-quote as an escape doesn't help — Python's triple-quoted string CONSUMES the backslash, turning it into just a bare single quote.

This breaks ALL inline event handlers that contain single quotes in ANY position:

| Pattern | Why it breaks |
|---------|--------------|
| `onclick="func('arg')"` | single-quote around arg ends the outer JS string |
| `onclick="window.open('/path', '_blank')"` | two single-quoted args, same root cause |
| `onclick="getElementById('id').click()"` | same mechanism |
| `onkeydown="if(event.key==='Enter')fn()"` | triple-embedded quotes, same root cause |

The root fix: **you cannot safely embed any onclick attribute value that contains single quotes inside a JS single-quoted string literal. Eliminate inline onclick entirely.**

## The Fix: Data Attributes + Event Delegation

**Never write inline onclick/onmouseover/onmouseout handlers in JS innerHTML strings.**

### Instead:
1. Add `data-action="action-name"` and parameter data attributes (`data-id`, `data-deal-id`, `data-stage`, etc.) to HTML elements
2. Use CSS `:hover` instead of onmouseover/onmouseout (with `!important` to override inline styles)
3. Handle all clicks in a single event delegation listener on `#centerPanel`

### Example:
```javascript
// DON'T:
html += '<div onclick="showDealDetail(\'' + d.id + '\')">...</div>';

// DO:
html += '<div data-action="view-deal" data-deal-id="' + d.id + '">...</div>';

// Then in the event delegation handler:
document.getElementById('centerPanel').addEventListener('click', function(e) {
  var t = e.target;
  var action = t.getAttribute && t.getAttribute('data-action');
  if (action === 'view-deal') { showDealDetail(t.dataset.dealId); return; }
});
```

### CSS for hover effects:
```css
.deal-card:hover { border-color: #D0D0D5 !important; }
.deal-card { transition: all 0.1s; }
```

### Modal pattern:
Use `class="modal-overlay"` for overlays, `data-action="close-modal"` for cancel buttons/backdrop, `data-action="stop-propagation"` for modal content.

**CRITICAL PITFALL: `data-action` elements inside modals appended to `document.body` will NOT fire the `#centerPanel` delegation handler.** The event delegation is only registered on `#centerPanel`, but modals are added to `document.body` (so they overlay the full page). Clicks on X buttons, Cancel buttons, and the overlay backdrop are invisible to the handler.

**Fix**: Add a self-contained click handler to the modal overlay right after inserting it into the DOM.

**Pattern A — `createElement` + `appendChild`** (gives you a direct reference):

```javascript
var modal = document.createElement('div');
modal.className = 'modal-overlay';
modal.innerHTML = '...';
document.body.appendChild(modal);

// Self-contained click handler — modals are outside #centerPanel
modal.addEventListener('click', function(e) {
  var a = e.target.getAttribute && e.target.getAttribute('data-action');
  if (a === 'close-modal') {
    modal.remove();
  } else if (a === 'stop-propagation') {
    e.stopPropagation();
  }
});
```

**Pattern B — `insertAdjacentHTML`** (when using HTML string, no reference returned):

```javascript
var modalHtml = '<div class="modal-overlay">...';
document.body.insertAdjacentHTML('beforeend', modalHtml);

// Get reference via lastElementChild — last child is what was just appended
var overlay = document.body.lastElementChild;
if (overlay && overlay.classList.contains('modal-overlay')) {
  overlay.addEventListener('click', function(e) {
    var a = e.target.getAttribute && e.target.getAttribute('data-action');
    if (a === 'close-modal') {
      overlay.remove();
    } else if (a === 'stop-propagation') {
      e.stopPropagation();
    }
  });
}
```

**Why `lastElementChild` is safe here:** The modal is appended last, and there should never be two modals open simultaneously. If overlapping modals become possible in the future, switch to Pattern A or use `document.querySelector` with a more specific selector.

Both patterns handle three close methods in one go:
1. ✕ close button → `data-action="close-modal"` on the button
2. Cancel button → `data-action="close-modal"` on the button  
3. Click on backdrop → `data-action="close-modal"` on the `.modal-overlay` div itself

**Closing the modal from other functions** (e.g., after a successful save/PATCH): use a class selector. Do NOT use fragile CSS attribute selectors:

```javascript
// RIGHT — uses the class that defines the modal
var modals = document.querySelectorAll('.modal-overlay');
for (var mi = 0; mi < modals.length; mi++) modals[mi].remove();

// WRONG — fragile CSS attribute selector that breaks if styling changes
var modal = document.querySelector('[style*="position:fixed"][style*="background:rgba"]');
if (modal) modal.remove();
```

### Non-click events (onchange, oninput, drag-drop):
Inline event handlers for non-click events (onchange, oninput, drag-drop) are **also** at risk. Use these patterns instead:

- **oninput on a search field**: Use `oninput="searchLeads()"` — this is safe because the attribute value has no single quotes. However, better practice is to use event delegation on 'input' events or `document.addEventListener('change', handler)`.
- **onchange on a `<select>` (cadence dropdown, etc.)**: Use `document.addEventListener('change', handler)` that checks for `data-action="change-cadence"`:
  ```javascript
  document.addEventListener('change', function(e) {
    var t = e.target.closest && e.target.closest('[data-action="change-cadence"]');
    if (!t) return;
    updateLeadCadence(t.dataset.leadId, e.target.value);
  });
  ```
  Pattern: add `data-action="change-cadence"` and `data-lead-id="..."` to the `<select>`, handle via change event delegation. No inline onchange needed.
- **onchange on a file input**: Use `document.addEventListener('change', handler)` that checks `e.target.id`:
  ```javascript
  document.addEventListener('change', function(e) {
    if (e.target.id === 'csvFileInput') {
      handleCSVFile(e.target.files[0]);
    }
  });
  ```
- **Drag-and-drop**: Two valid approaches:

  **Approach A — Event listeners** (for simple cases, works when elements exist at listener registration time):
  ```javascript
  document.addEventListener('drop', function(e) { e.preventDefault(); /* handle */ });
  document.addEventListener('dragover', function(e) { e.preventDefault(); });
  ```
  Use `e.target.closest('.deal-dropzone')` to find the right container.

  **Approach B — Inline handlers with data attributes** (for dynamically created innerHTML elements, avoids quoting by using `e.currentTarget.dataset` instead of inline arguments):
  ```javascript
  // In the innerHTML string — NO inline arguments, NO quotes in attribute value:
  html += '<div class="deal-dropzone" data-stage="' + stage + '" ondragover="dragOver(event)" ondrop="dropDeal(event)" ondragleave="dragLeave(event)">...</div>';
  html += '<div class="deal-card" draggable="true" data-deal-id="' + d.id + '" ondragstart="dragDeal(event)">...</div>';

  // Handler functions read data from e.currentTarget.dataset (not from inline args):
  function dragDeal(e) {
    e.dataTransfer.setData('text/plain', e.target.dataset.dealId);
    e.target.classList.add('dragging');
    e.target.style.opacity = '0.4';
  }
  function dragOver(e) {
    e.preventDefault();
    e.currentTarget.classList.add('drag-highlight');
  }
  function dropDeal(e) {
    e.preventDefault();
    var dealId = e.dataTransfer.getData('text/plain');
    var stage = e.currentTarget.dataset.stage;
    // ... use dealId and stage without any quoting issues
  }
  function dragLeave(e) {
    e.currentTarget.classList.remove('drag-highlight');
  }
  ```

  **Key insight:** `data-stage="' + stage + '"` and `data-deal-id="' + d.id + '"` are safe because string values are interpolated BEFORE the attribute value quotes — the single-quoted JS strings only contain variable names and string literals with no embedded quotes like `'reachout'`. Compare:
  - ❌ DANGEROUS: `ondrop="dropDeal(event, 'reachout')"` — has single quotes inside the attribute value → breaks JS innerHTML string
  - ✅ SAFE: `ondrop="dropDeal(event)"` and `data-stage="reachout"` with `e.currentTarget.dataset.stage` — no quotes in the attribute value

  **Rule: When an event handler needs data, put the data in a `data-*` attribute (interpolated before the attribute's quotes are parsed) and read it via `e.currentTarget.dataset` in the handler. Never pass arguments with quotes inside inline event handler attributes in JS innerHTML strings.**
- **Modal overlay click (close on click-outside)**: Set `data-action="close-modal"` on the overlay div and handle in the click delegation handler.

### Utility Functions for Safe innerHTML

When building HTML strings in JS and assigning to `innerHTML`, any user-provided data (lead names, company names, notes, tooltip text) must be HTML-escaped. **Define a shared `esc()` function at the top of the script block:**

```javascript
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
```

### Where to use it

- Any `data-action` attribute value that includes user data
- Tooltip text content (`.cad-tooltip`, etc.)
- Any `innerHTML += '...'` concatenation that interpolates API response data

### Common failure mode

Calling `esc()` when it doesn't exist crashes the entire `innerHTML` assignment in the `try` block, which then falls into the `catch` block and shows a generic error page. **Always define `esc()` before any function that uses it.**

### Where to define it

In the `<script>` block of `dashboard_template.py`, just below the event delegation handler — NOT inside a DOMContentLoaded wrapper, so it's globally accessible:

```javascript
// ── Utility: HTML escape ──
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

// ── Cadence UI ──
function cadenceHTML(l) { ... uses esc(tipText) ... }
```

### Check before adding a new UI section

Before adding any new innerHTML-injecting function that interpolates data:
1. Does it use `esc()` on user-facing strings? If not, add it.
2. Does `esc()` already exist in the script block? If not, define it first.
3. Did you verify with a real API call that the function runs without throwing?

## File input trigger pattern:
When a dropzone element needs to trigger a hidden file input's `.click()`, use a dedicated data-action:

```javascript
// HTML (in innerHTML):
'<div class="dropzone" data-action="open-csv-file">...'

// Event delegation handler:
if (action === 'open-csv-file') {
  document.getElementById('csvFileInput')?.click();
  return;
}

// File change event (separate from click delegation):
document.addEventListener('change', function(e) {
  if (e.target.id === 'csvFileInput') {
    handleCSVFile(e.target.files[0]);
  }
});
```

### Event delegation pitfall: elements with children (tables, cards)

When using event delegation, `e.target` is the most deeply nested element that received the click — typically a `<td>` cell in a table or a child `<span>` inside a card. **Never check `e.target.classList.contains('my-class')` on parent elements — it will always miss.**

```javascript
// WRONG — clicks land on <td>, not <tr class="lead-row">
document.getElementById('centerPanel').addEventListener('click', function(e) {
  if (e.target.classList.contains('lead-row')) {  // NEVER true
    showLeadDetail(e.target.dataset.id);
  }
});

// RIGHT — use closest() to walk up the DOM
document.getElementById('centerPanel').addEventListener('click', function(e) {
  var row = e.target.closest('.lead-row');
  if (row) {
    showLeadDetail(row.dataset.id);
  }
});
```

This applies to ALL delegated elements that contain child nodes:
- `<tr class="lead-row">` → click lands on `<td>` inside
- `<div class="deal-card" onclick>` → click lands on `<span>` or text node inside
- Any element with clickable children

**Rule of thumb**: if the delegated element can contain text nodes or child elements, always use `closest()` instead of `classList.contains()`.

### Data attribute naming convention:
- `data-action` — canonical action name (kebab-case)
- `data-id` — generic ID
- `data-deal-id`, `data-lead-id`, `data-stage` — specific context
- `data-action-id` — action item ID
- `data-filter` — filter value
- `data-cat` — category filter

### PITFALL: `data-action` on parent elements catches clicks from child inputs

When a delegated click handler uses `e.target.closest('[data-action]')` on elements that contain interactive children (inputs, textareas, select, buttons), clicks on those children will bubble up and trigger the parent's action. This causes:

1. The parent's handler fires (e.g., step selection, card expand)
2. Full DOM re-render
3. Input loses focus — user can't type

**The fix:** Check the actual clicked element's tag before dispatching:

```javascript
} else if (action === 'select-step') {
  var clickedEl = e.target;
  if (clickedEl.tagName === 'INPUT' || clickedEl.tagName === 'TEXTAREA' || clickedEl.tagName === 'SELECT' || clickedEl.tagName === 'BUTTON') return;
  selectStep(parseInt(t.dataset.stepIndex));
}
```

This pattern applies to ANY delegated handler where clickable containers (cards, rows, panels) contain form elements. Always check: "Could the user click an input/button inside this container and trigger the wrapper's action?"

### PITFALL: Embedding `<script>` tags inside innerHTML won't execute

Browsers do NOT execute `<script>` tags inserted via `innerHTML` — this is a security feature to prevent script injection. If you inject HTML that contains `<script>loadActionsForLead(...)</script>`, the function will never fire.

**Wrong pattern:**
```javascript
container.innerHTML = '...' +
  '<script>loadActionsForLead(\'' + leadId + '\');</script>';
// Script never executes — actions tab shows "Loading…" forever
```

**Correct pattern — call the function directly after innerHTML:**
```javascript
container.innerHTML = '...';
// Call the async population function directly — NOT via a script tag
loadActionsForLead(leadId);
```

This applies to ANY dynamically-loaded tab content, not just actions. The pattern is: set innerHTML for the skeleton, then call the async loader function in the same turn.

## Undefined Variable in innerHTML Template String

A variable referenced inside a JS template string (`html += '...' + someVar + '...'`) that was **never defined** in the function scope causes a `ReferenceError`. Because this typically happens inside a `.then()` callback, the error is **swallowed** by the `.catch()` handler, which shows a generic "Error loading X" message instead of the real error.

**Always check the browser console, not just the visible UI.** The console will show `ReferenceError: X is not defined`. The visible error message is a red herring.

See `references/undefined-variable-in-html-template.md` for the full debugging path, root cause analysis, and prevention checklist.

## When Inline onclick IS Safe

Not all inline onclick calls are dangerous. The rule: **inline onclick is safe when the attribute value contains no single quotes.**

```javascript
// SAFE — no quotes in the attribute value
onclick="addStep()"
onclick="resetTemplate()"
onclick="publishCadence()"

// DANGER — has single quotes inside
onclick="console.log('hello')"
onclick="selectTemplate('id')"     // ← this is what keeps breaking
onkeydown="if(event.key==='Enter')fn()"
```

This distinction matters because ARA has TWO types of template files:

| File type | How HTML is built | onclick risk |
|-----------|------------------|-------------|
| `dashboard_template.py`, `threads_template.py` | JS `innerHTML` via `html += '...'` | **Always use data-action** — single-quote string delimiters make any inline onclick with arguments dangerous |
| `cadence_template.py` | Static HTML (direct in Python string) | Hybrid OK — simple `onclick="fn()"` is safe, but `data-action` still preferred for dynamic data |

### Cadence Builder pattern

The Cadence page demonstrates the correct hybrid approach:
- **Template cards** use `data-action="select-template"` with global delegation — handles dynamic data (template IDs) without quoting risk
- **Utility buttons** (Publish, Reset, Add Rule, Delete, Custom Toggle) use `onclick="funcName()"` — no arguments = no quotes = safe
- **Channel chip drag** uses native `draggable` + `ondragstart="onChannelDragStart(event)"` — safe because the attribute value has no quotes
- **Input type="file" and onchange** use document-level listeners — no inline handlers

### Lead Chat Thread Pattern

See `references/lead-chat-thread-pattern.md`.

Creating a dedicated "Chat about {{lead_name}}" thread from the lead detail page uses:
- `data-action="start-lead-chat" data-lead-id="{{id}}"` on the button (not inline onclick)
- Event delegation: `if (action === 'start-lead-chat' && t.dataset.leadId) { startLeadChat(t.dataset.leadId); return; }`
- Backend: `POST /api/leads/{lead_id}/chat` creates the thread and returns lead data + past conversations
- The `startLeadChat()` function clears the current chat, sets the new thread, and sends lead context as the first message — all async, all error-handled.

### CRITICAL PITFALL: Python triple-quoted string escape processing

This is the #1 most common JS-in-Python-template error, and it silently produces garbage JS that `node -c` catches.

### The problem

ARA's template files use Python `"""..."""` strings. Python processes ALL escape sequences inside these strings **before** the browser sees the JavaScript.

| You write in file | Python produces in HTML | JS interprets as | Valid? |
|---|---|---|---|
| `\n` | actual newline (0x0A) | breaks string across lines | ❌ SyntaxError |
| `\\n` | `\n` (backslash + n, 0x5C 0x6E) | JS newline escape | ✅ |
| `\\"` | `\"` (backslash + quote) | escaped double-quote | ✅ |
| `\\\\` | `\\` (two backslashes) | escaped backslash | ✅ |

**Tracing the levels (this is the mental model):**

```
Your patch tool call → Python file       → Python """...""" parser → HTML served
   \\n              → file has \n (1 \ )  → Python sees escape    → newline (0x0A) ❌
   \\\\n            → file has \\n (2 \\) → Python sees \\ → \    → \n in HTML ✅
   \\\\\\\\n         → file has \\\\n (4 \) → Python sees \\\\ → \\ → \\n in HTML ❌ (wrong for JS)
```

**In practice — what to type in the patch/new_string parameter:**

| You want in HTML | Type in patch parameter |
|---|---|
| `\n` (newline escape) | `\\\\n` (4 backslashes + n) |
| `\\n` (literal backslash-n) | `\\\\\\\\n` (8 backslashes + n) |
| `\"` (escaped double-quote in JS) | `\\\\\"` (4 backslashes + quote) |
| literal double-quote `"` | `\"` (escaped in patch JSON) |

### The safe workaround: use double quotes for JS strings

Inside Python `"""..."""`, double-quoted JS strings (`"..."`) are much safer than single-quoted (`'...'`) because:
- `\n` inside `"..."` JS strings is a valid newline escape
- `\n` inside `'...'` JS strings is ALSO a valid newline escape
- But the double-quote method avoids the quoting trap with `\"` inside the Python string

However, you still need `\\n` (not `\n`) in the Python source, which means:
- In the file: `\\n` (2 backslashes + n)
- In the patch tool: `\\\\n` (4 backslashes + n as a string parameter)

### Nuclear option: binary replacement when patch escaping fails

When the patch tool's escaping produces inconsistent results (the `\\n` / `\\\\n` / `\\\\\\n` multiplication problem), use direct binary replacement as a last resort:

```python
# Read the file, replace bytes directly, write back
with open('/path/to/file.py', 'rb') as f:
    data = f.read()

# Replace single backslash-n (0x5C 0x6E) with double backslash-n (0x5C 0x5C 0x6E)
# This is what you need for `\n` inside a Python """...""" string to
# produce `\n` (valid JS escape) in the HTML output
data = data.replace(b'\\n', b'\\\\n')

with open('/path/to/file.py', 'wb') as f:
    f.write(data)

# Verify with hex dump:
python3 -c "
with open('/path/to/file.py', 'rb') as f:
    d = f.read()
idx = d.find(b'your_target_string')
chunk = d[idx:idx+30]
print('Hex:', chunk.hex())
# Expected: 5c5c6e for \\n (double backslash + n)
# Wrong: 5c6e for \n (single backslash = Python newline escape)
# Wrong: 5c5c5c5c6e for \\\\n (quadruple backslash = too many)
"
```

### Root cause summary (the full escaping stack)

| Layer | Input | Processing | Output |
|-------|-------|-----------|--------|
| 1. Patch tool parameter | `\\n` | patch writes literal bytes | File gets `\n` (1 backslash) |
| 2. Python `"""..."""` string | `\n` in file | Python escape processing | newline 0x0A ❌ |
| | | | |
| 1. Patch tool parameter | `\\\\n` | patch writes literal bytes | File gets `\\n` (2 backslashes) |
| 2. Python `"""..."""` string | `\\n` in file | Python sees `\\` -> `\` | `\n` in runtime string ✅ |
| | | | |
| 1. Binary replacement | `replace(b'\\n', b'\\\\n')` | byte-level | File has `\\n` (2 backslashes) ✅ |
| 2. Python `"""..."""` string | `\\n` in file | Python sees `\\` -> `\` | `\n` in runtime string ✅ |

**Key insight:** The file must contain `\\n` (2 backslash characters, bytes 0x5C 0x5C 0x6E) in order for Python's `"""..."""` parser to produce `\n` (backslash + n) in the runtime string. If the file has `\n` (1 backslash), Python treats it as a newline escape. If the file has `\\\\n` (4 backslashes), Python produces `\\n` (2 backslashes) in the output — wrong for JS.

### Verification for new ARA template files

See `references/triple-quote-escaping-tight-loop.md` for a full debugging walkthrough from a real session.

After writing any new `<script>` block inside a Python triple-quoted string:

```bash
# 1. Extract JS from the HTML served by the running server
curl -s http://localhost:8766/YOUR_PAGE | python3 -c "
import sys, re
html = sys.stdin.read()
m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
if m:
    with open('/tmp/check.js', 'w') as f:
        f.write(m.group(1))
"
# 2. Verify syntax
node -c /tmp/check.js  # must exit 0 with no SyntaxError

# 3. If SyntaxError, use xxd to check exact bytes at the failing line
sed -n '1392,1396p' /tmp/check.js | xxd
# If you see 0x5C6E (backslash-n) split as actual newline 0x0A, you hit the trap
# Fix: use binary replacement to add one more backslash
```

### Common symptoms

| Symptom | Likely cause |
|---------|-------------|
| `node -c` SyntaxError at a line with `\n` inside a string literal | Single `\n` in file → Python ate it as an escape → actual newline in HTML |
| `node -c` SyntaxError: "Unexpected string" | Inline onclick has unescaped nested quotes — see event delegation fix above |
| HTML renders but JS event handlers don't fire | `data-action` element not matching the delegation handler's selector, or element is outside `#centerPanel` |

## Autocomplete/Searchable Dropdowns in Modals

See `references/autocomplete-modal-pattern.md` for the proven pattern: data-attribute-driven dropdown items, click delegation with `e.target.closest()`, attaching listeners INSIDE the modal function (not global scope).

**All ARA standalone pages (Cadence, Threads) must share the exact same 8-item sidebar as the dashboard SPA.** Missing nav items (Knowledge, Induction, Integrations) is a common bug — always verify.

See `references/standalone-page-layout.md` for sidebar HTML template, nav link conventions, CSS block, Ava chat panel requirements, and common pitfalls.

## Hash Routing for SPA Navigation from Standalone Pages

When standalone pages (cadence page, threads page) have sidebar nav items that need to navigate to the dashboard SPA's internal pages (Knowledge, Induction, Integrations), use hash routing:

```javascript
// ── URL hash routing on dashboard load ──
(function() {
  var hash = window.location.hash.replace('#', '');
  if (hash && ['leads','deals','activities','actions','knowledge','induction','integrations','threads'].indexOf(hash) >= 0) {
    var checkReady = setInterval(function() {
      if (typeof showPage === 'function') {
        showPage(hash);
        clearInterval(checkReady);
      }
    }, 50);
    setTimeout(function() { clearInterval(checkReady); }, 5000);
  }
})();
```

### How it works

1. **Standalone page nav item** uses `window.location='/dashboard#knowledge'` (not `window.location='/knowledge'`)
2. The dashboard SPA loads at `/` (which serves `dashboard_template.py`)
3. Hash routing polls every 50ms for `showPage()` to be defined (the SPA JS takes a moment to initialize)
4. Once available, it calls `showPage('knowledge')` to navigate to the correct internal page
5. 5-second timeout prevents infinite polling if something goes wrong

### Adding new SPA pages to the hash router

When adding a new internal page (e.g., `showPage('settings')`):

1. Add the page name to the `indexOf` array in the hash routing code
2. The standalone page nav link uses `/dashboard#settings`
3. No other changes needed — the routing is generic

### Sidebar nav link conventions per page

| Page | Nav pattern | Target |
|------|------------|--------|
| Dashboard SPA (`/`) | `showPage('knowledge')` | Same SPA — direct function call |
| Cadence Builder (`/cadence`) | `window.location='/dashboard#knowledge'` | Hash route to SPA |
| Threads (`/threads`) | `window.location='/dashboard#knowledge'` | Hash route to SPA |

The SPA pages (Knowledge, Induction, Integrations) only render inside the dashboard SPA's `centerPanel` — they don't have standalone routes. Hash routing is the only way to navigate to them from an external page.

### Pitfall: showPage() must be defined before hash routing fires

The dashboard SPA defines `showPage()` inside a `<script>` block at the bottom of the HTML. The hash router must poll because `showPage()` may not exist synchronously if the script is still loading. The 50ms polling interval catches it within 1-2 iterations on a warm page load.

### Pitfall: hash route to threads page

The threads page is now a standalone page (not an SPA page), so its sidebar nav uses `window.location='/threads'` — NOT `showPage('threads')` or hash routing. Don't add 'threads' to the hash router's page list unless it becomes an SPA page in the future.

### Pitfall: fetch() defaults to GET, not POST

When calling a backend endpoint that uses `@app.post()`, the frontend `fetch(url)` defaults to GET. The call silently returns `undefined` or a 405:

```javascript
// WRONG — defaults to GET, post endpoint returns nothing
var r = await fetch('/api/leads/' + leadId + '/chat');

// RIGHT — specify method: POST
var r = await fetch('/api/leads/' + leadId + '/chat', {method: 'POST'});
| `\x27` (JS hex-escaped single quote) | `\\\\x27` (4 backslashes + x27) |

This is especially easy to miss when:
- You wrote the POST endpoint yourself and know it exists
- You call it via `fetch(url)` out of habit (fetch defaults to GET)
- The endpoint returns immediately (GET hits the POST route which returns `null` or `405`)
- The JS catches no error — it gets a response, just not the expected one

**Verification:** Always curl-test the endpoint separately first. Then in the browser console fetch directly and log the response. If `data.thread_id` is `undefined`, check if you forgot the method override.

### PITFALL: Python hex escapes (`\xNN`) are consumed by the string parser, same as backslash-letter escapes

This is the #2 most common JS-in-Python-template error (after the `\n` → newline trap above).

**The problem:** Python processes `\xNN` hex escapes inside `"""..."""` strings **the same way it processes `\n` and `\t`**. `\x27` in a Python string literal produces the actual single-quote character (U+0027), **not** the literal bytes `\x27`.

```python
# Python source code:
x = 'cancelAction(\x27 + a.id + \x27)'
# Python evaluates this as:
#   'cancelAction(' + a.id + ')'
# Because \x27 → ' (single quote character)
```

This means in ARA's template files, writing `cancelAction(\x27 + a.id + \x27)` inside a `"""..."""` string produces `cancelAction(' + a.id + ')` in the HTML output — the exact same broken JS that inline `'` caused.

**The fix:** Double the backslash so Python outputs literal `\x27`:

```python
# Python source code — note the doubled backslash:
x = 'cancelAction(\\x27 + a.id + \\x27)'
# Python evaluates as:
#   'cancelAction(\x27 + a.id + \x27)'
# Output: cancelAction(\x27 + a.id + \x27)
# JS then interprets \x27 as ' → cancelAction('xyz')
```

**How to write it in the file:**

| You want in HTML | Python source file must have | Patch tool parameter |
|---|---|---|
| `\x27` | `\\x27` (2 bytes: 0x5C 0x78 0x32 0x37) | `\\\\x27` (4 backslashes + x27) |
| `\x22` | `\\x22` | `\\\\x22` |
| `\n` | `\\n` | `\\\\n` |
| `\t` | `\\t` | `\\\\t` |

**Verification by reading the source file:**

```bash
# Check what's actually in the Python source file:
grep -n 'x27' dashboard_template.py | head -5
# If you see \\x27 (double backslash) → correct
# If you see \x27 (single backslash) → Python will eat it
```

**Verification by checking the served output (END-TO-END — always do this):**

Never trust that the source file fix propagated. Always verify against the actual HTML the server sends:

```bash
# 1. Restart the server after edits
# 2. Fetch the page and extract JS
curl -s http://localhost:8766/ | python3 -c "
import sys, re
html = sys.stdin.read()
m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
if m:
    with open('/tmp/ara_check.js', 'w') as f:
        f.write(m.group(1))
        print('Wrote /tmp/ara_check.js with', len(m.group(1)), 'bytes')
"

# 3. Check syntax
node -c /tmp/ara_check.js

# 4. If it fails, find the line and hex-dump it
#    (because \x27 becomes ' which is invisible in terminal output)
node -c /tmp/ara_check.js 2>&1 | grep -o 'line [0-9]*' | cut -d' ' -f2 | head -1 | xargs -I{} sh -c "sed -n '{}p' /tmp/ara_check.js | xxd | head -10"

# If you see a bare 0x27 at the position where \x27 should be, Python ate it.
# Fix: double the backslash in the Python source file.
```

**Why you must check the served output, not the source:**

The server process may have loaded the old `.pyc` cache. After editing a Python template file, you must **restart the Python server process** — not just reload the page — to pick up changes. Even then, `.pyc` files in `__pycache__/` may serve stale bytecode. `find . -name '__pycache__' -exec rm -rf {} +` before restart for confidence.

```bash
# Nuclear option — clear all caches and restart
find /Users/greg/ara -name '__pycache__' -exec rm -rf {} + 2>/dev/null
# Kill old server, start fresh
lsof -ti :8766 | xargs kill -9 2>/dev/null
python3 /Users/greg/ara/server.py &
sleep 2
# Then verify with the curl → node pipeline above
```

**Common symptom:**

| Symptom | Likely cause |
|---------|-------------|
| Source file has `\\x27` but node --check still shows `'` breaking the JS | Server is running old `.pyc` — restart it, or delete `__pycache__/` |
| `xxd` shows `0x27` byte where you expect `5c 78 32 37` | Python ate the hex escape — file has single backslash `\x27` instead of double `\\x27` |
| Function call in output looks like `cancelAction('' + id + '')` | Embedded `\x27` was consumed by Python → output has `'` which closes the outer JS string

## Production UI Icon Pattern

For channel chips, step rows, and any visual element in production UI, use colored SVG icon wraps instead of emoji. See `references/svg-channel-icons.md` for:
- CSS patterns (icon wrap sizing per context)
- SVG source strings (WhatsApp green, Email blue, Call indigo, SMS gray)
- Usage in HTML (channel chips) and JavaScript (CHANNEL_ICONS object for step rendering)
- Anti-patterns (emoji in production, mixed icon sizes, wrong stroke colors)

## When Inline onclick IS Safe
