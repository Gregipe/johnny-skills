# Prompt Builder Save/Load Debugging Patterns

Failure modes when the full-screen Prompt Builder fails to save data or loses it on refresh.

## Pattern 1: Prefill Overwrite (Lost Saved Data on Refresh)

**Symptoms:** User enters data in Brand tab, clicks Save Changes, sees "✓ Saved to draft". On refresh, data is gone. Brand fields are empty or show only default values.

**Root cause:** `loadPromptBuilderData()` checks if sector data exists. If empty, it fetches prefill from `/api/cadence/prefill`. The prefill response does `t.promptParts = pf` — a complete overwrite that nukes any saved brand data.

**The fix:** Deep merge instead of replace:

```javascript
// WRONG — overwrites all saved data
t.promptParts = pf;

// RIGHT — only fill empty fields from prefill
for (var section in pf) {
  if (!t.promptParts[section] || Object.keys(t.promptParts[section]).length === 0) {
    t.promptParts[section] = pf[section];
  } else {
    for (var field in pf[section]) {
      if (!t.promptParts[section][field]) {
        t.promptParts[section][field] = pf[section][field];
      }
    }
  }
}
```

**Verification:** After refresh + reopen, check `document.querySelector('#pe_personality').value` — should show previously saved text.

## Pattern 2: JS Scope Bug — pb is not defined in gvPbVal

**Symptoms:** Clicking "Save Changes" does nothing. No error message shown. The `else` branch (validate-first) fires but silently fails.

**Root cause:** `gvPbVal(id)` references `var el = pb.querySelector('#' + id)` but `pb` was only defined inside `applyPbData()` as a local variable. `gvPbVal` is a standalone function — it doesn't have `pb` in scope.

**The fix:** Self-contained element lookup:

```javascript
function gvPbVal(id) {
  var pb = document.getElementById('pbOverlay');
  if (!pb) return '';
  var el = pb.querySelector('#' + id);
  return el ? el.value : '';
}
```

**Verification:** Call `savePromptBuilder()` from console — should execute without throwing `ReferenceError: pb is not defined`.

## Pattern 3: Cross-Page JS Environment (bwConfirm Undefined)

**Symptoms:** Close button, backdrop click, and "← Back to Cadence" all fail to close the builder. No error visible to user.

**Root cause:** The B&W modal system (`bwConfirm`) was added to `dashboard.js`, but the cadence page does NOT load `dashboard.js`. The cadence page has its own inline `<script>` in `prompt_builder_template.py`. When `closePromptBuilder()` calls `window.bwConfirm(...)`, it throws `TypeError` and JS execution stops.

**The fix:** Inline the shared functionality in each page's script with a guard to avoid duplicates:

```javascript
(function() {
  if (document.getElementById('bwDialog')) return; // already created
  // ... create dialog ...
  if (!window.bwConfirm) {
    window.bwConfirm = function(msg) { ... };
  }
})();
```

**Verification:** Open builder on cadence page → click backdrop → confirm dialog appears centered.

## Pattern 4: Silent API Failures (No Error Handling)

**Symptoms:** User clicks Save Changes, button shows "⏳ Saving..." briefly, then nothing. No success, no error.

**Root cause:** `fetch()` calls had no `.catch()` handler. If the API returned an error or the network failed, the Promise rejected silently.

**The fix:** Always chain `.catch()` on every fetch in the save flow, with a status bar error message:

```javascript
fetch('/api/cadence/save-draft', { ... })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (data.status === 'ok') { showSuccess(); }
    else { showError(data.error || 'server error'); }
  })
  .catch(function(err) {
    showError('Save failed: ' + err.message);
  });
```

## Pattern 5: Missing Button ID for Loading State

**Symptoms:** User clicks Save Changes, button doesn't change to "⏳ Saving..." — nothing visually indicates work is happening.

**Root cause:** The selector `document.querySelector('button[onclick*="savePromptBuilder"]')` is fragile. Multiple buttons with `onclick="savePromptBuilder()"` exist in the DOM (inline builder + full-screen builder).

**The fix:** Add a unique `id` attribute to the button:

```html
<button class="pb-btn" id="pbSaveBtn" onclick="savePromptBuilder()">Save Changes</button>
```

Then reference by ID: `document.getElementById('pbSaveBtn')`.

## Prevention Checklist

When adding or fixing any form save/load flow:

- [ ] Does the save function have `.catch()` on all fetch calls?
- [ ] Does the load function check the SPECIFIC missing field and MERGE, not replace?
- [ ] Are all utility functions self-contained (no closure-scope variable dependencies)?
- [ ] Does shared JS functionality work on ALL pages that include it?
- [ ] Does the Save button have a unique ID for loading state?
- [ ] Do ALL fetch paths update the UI (success AND error)?
