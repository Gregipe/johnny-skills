# Prompt Builder Save Flow & Unsaved Changes Warning

## Save Flow (as of May 2026)

### The Two Paths

**Path A — Already validated:** If user has clicked Validate & Compile, pbFinalPrompt has the compiled text. Save Changes sends it to POST /api/cadence/save-draft, calls saveCurrentState(). Toast: "✓ Saved to draft".

**Path B — Never validated:** User types fields, clicks Save Changes before validating. pbFinalPrompt still shows placeholder text. Old code hit an `else` that called validateAndCompilePrompt() but NEVER called save-draft or saveCurrentState(). Data existed only in memory. Refresh = lost.

**Fix:** The else branch now validates, chains into save-draft, calls saveCurrentState, sets pbDirty=false.

```javascript
// Path B — validate then chain into save
fetch('/api/cadence/validate', {
  method: 'POST',
  body: JSON.stringify({ template_id: t.id, promptParts: parts })
})
.then(r => r.json())
.then(data => {
  if (data.status === 'ok') {
    promptPartsCache = parts;
    document.getElementById('pbFinalPrompt').textContent = data.compiled_prompt;
    t.systemPrompt = data.compiled_prompt;
    return fetch('/api/cadence/save-draft', {
      method: 'POST',
      body: JSON.stringify({ template_id: t.id, promptParts: parts, systemPrompt: t.systemPrompt })
    });
  }
})
.then(r => r && r.json())
.then(data => {
  if (data && data.status === 'ok') {
    saveCurrentState();
    window.pbDirty = false;
  }
});
```

#### Critical: Button Loading / Error States

The save function must update the actual clicked button (saveBtn), not a secondary element:
- On click: `saveBtn.textContent = '⏳ Saving...'` and `saveBtn.disabled = true`
- Set `document.getElementById('promptEditorStatus').textContent = ''` to clear previous status
- On success: `if (s) s.textContent = '✓ Saved to draft'`
- On error: `if (s) s.textContent = '✖ Save failed: ' + (err.message || 'error')`
- **Every fetch path MUST have `.catch()`** — silent failures are unacceptable.

The Save Changes button needs an ID (`id="pbSaveBtn"`) for reliable querySelector access. The `onSaveDone()` helper restores button text after both success and error.

**Error path in the "already validated" branch:**
```javascript
.then(function(data) {
  onSaveDone();
  if (data.status === 'ok') {
    saveCurrentState();
    window.pbDirty = false;
    if (s) s.textContent = '✓ Saved to draft';
  } else {
    if (s) s.textContent = '✖ Save failed: ' + (data.error || 'server error');
  }
})
.catch(onSaveError);
```

**Error path in the "validate first" branch:**
```javascript
.then(function(data) {
  if (data.status === 'ok') {
    // ... validate + save-draft chain
  } else {
    onSaveDone();
    if (s) s.textContent = '✖ Validation failed';
    return null;
  }
})
```

### gvPbVal Scope Trap

`gvPbVal(id)` and `setPbVal(id, val)` are helper functions that query elements inside `#pbOverlay` using `pb.querySelector(...)`. These are defined as **standalone functions** — they do NOT inherit variables from callers.

```javascript
// ❌ BROKEN — pb is not defined here
function gvPbVal(id) {
  var el = pb.querySelector('#' + id);  // ReferenceError: pb is not defined
  return el ? el.value : '';
}
```

`pb` was only defined locally inside `applyPbData()`. When `collectPbParts()` called `gvPbVal()`, `pb` didn't exist in scope. **Fix:** look up `pb` inside each helper:

```javascript
function gvPbVal(id) {
  var pb = document.getElementById('pbOverlay');
  if (!pb) return '';
  var el = pb.querySelector('#' + id);
  return el ? el.value : '';
}
```

(Note: `setPbVal` already had this fix — only `gvPbVal` was missing it.)

### Warning: Cadence Page Doesn't Load dashboard.js

The `/cadence` page is served from `cadence_template.py` — it does NOT include `<script src="/static/dashboard.js">`. Any JS shared between the dashboard page and the cadence page must be inlined in `prompt_builder_template.py` or added to both templates separately.

**Impact on B&W modal:** The `bwConfirm`/`bwAlert` functions defined in dashboard.js are NOT available on the cadence page. The prompt builder template inlines a duplicate of the modal code with a guard (`if (document.getElementById('bwDialog')) return`) so it works on both pages without creating duplicate `<dialog>` elements.

## Save vs Publish (May 30 2026 Update)

| Button | Backend | Effect |
|--------|---------|--------|
| Save Changes | POST /api/cadence/save-draft | Persists draft. Does NOT change live cadence. |
| Publish | Validates first, then calls POST /api/cadence/publish | Calls `/api/cadence/validate` first. If status `ok`, proceeds to publish. If contradictions found, shows them in the Final tab and stops — does NOT publish. No separate Validate button exists anywhere in the builder. |

**Publish = validate + publish in one click.** The standalone Validate button was removed from both the top bar and the Final tab. The top bar now shows only `Save Changes | Publish | ✕`.

### Publish Flow

```javascript
function publishPromptBuilder() {
  // 1. Collect prompt parts
  var parts = collectPbParts();
  // 2. Validate first
  fetch('/api/cadence/validate', { body: JSON.stringify({ template_id: 'global', promptParts: parts }) })
    .then(r => r.json())
    .then(function(data) {
      if (data.status === 'ok') {
        // Update compiled prompt in DOM, then publish
        document.getElementById('pbFinalPrompt').textContent = data.compiled_prompt;
        fetch('/api/cadence/publish', { body: JSON.stringify({ ... }) })
          .then(r => r.json())
          .then(function(pubData) {
            if (pubData.status === 'ok') {
              saveCurrentState();
              window.pbDirty = false;
              // Close builder, reload templates
            }
          });
      } else {
        // Validation failed — show contradictions, switch to Final tab, don't publish
        renderContradictions(data.contradictions);
        switchPbTab('final');
      }
    });
}
```

### Final Tab Auto-Compile

The Final tab auto-compiles when visited — no button needed:

```javascript
function switchPbTab(tabId) {
  // ... tab switching logic ...
  if (tabId === 'final') {
    setTimeout(function() { validateAndCompilePrompt(); }, 300);
  }
}
```

The placeholder shows "Compiling prompt — this updates automatically when you visit this tab." which changes to "⏳ Compiling prompt..." during the API call, then the compiled text once the LLM responds (~20s).

### Final Tab Buttons

The Final tab now shows only:
- **📋 Copy** — copies compiled prompt to clipboard
- **↓ Export** — downloads as .txt

The **Validate & Compile** button was removed (merged into Publish). The section chips (Full/Brand/Sector/Security/Channels) remain for visual filtering.

## Unsaved Changes Warning

Added May 2026. Three guards:

1. **Close guard** — closePromptBuilder() checks window.pbDirty. If dirty, shows bwConfirm before closing.
2. **Escape key** — Same guard via pbKeyHandler.
3. **beforeunload** — Page refresh triggers browser's native leave warning.

### Dirty Flag Reset Points

| Event | Action |
|-------|--------|
| Builder opens | window.pbDirty = false |
| Any input/change in #pbOverlay | window.pbDirty = true |
| Save Changes succeeds | window.pbDirty = false |
| Publish succeeds | window.pbDirty = false |

## Adding a New Field to the Prompt Builder

Must update ALL six surfaces:

1. HTML input/textarea in prompt_builder_template.py
2. collectPbParts() in prompt_builder_template.py (save)
3. applyPbData() in prompt_builder_template.py (load)
4. assembleSystemPrompt() in cadence_template.py (compile into prompt)
5. Validate endpoint prompt in server.py (/api/cadence/validate)
6. Prefill data model in prefill_generator.py (defaults)
