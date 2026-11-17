# ARA Prompt Builder — Full Persistence Chain Map

## The Chain (click → persistence)

```
savePromptBuilder()
  → getTemplate()              # TEMPLATES[currentTemplateId] (in-memory from localStorage)
  → collectPbParts()           # Reads form field values via DOM
  → gvPbVal(id)                # pb.querySelector('#' + id).value  [SCOPE BUG: needed own var pb]
  → compiled = pbFinalPrompt   # DOM element textContent
  →                           # CHECK: compiled === placeholder?
  →   if compiled exists:      # Direct save-draft API call
  →   else:                    # Validate first, then save-draft
  →     /api/cadence/validate  # LLM call → returns compiled prompt + contradictions
  →     /api/cadence/save-draft # Persists promptParts + systemPrompt to DB
  →     saveCurrentState()     # Saves to localStorage via saveData()
  →     pbDirty = false        # Resets unsaved changes flag
  →     status bar update      # "✓ Saved to draft" feedback
```

## Bugs Found (in order)

### Bug 1: gvPbVal scope crash
**File:** `prompt_builder_template.py`  
**Sign:** Save silently does nothing, no console error  
**Root:** `gvPbVal(id)` used `pb` variable that only existed in `applyPbData()`'s closure  
**Fix:** Added `var pb = document.getElementById('pbOverlay');` at top of `gvPbVal()`

### Bug 2: Prefill overwrites saved data on refresh
**File:** `prompt_builder_template.py` line ~872  
**Sign:** Save works (API + DB), data gone on page refresh  
**Root:** `loadPromptBuilderData()` checks `pp.sectorSpecific.valueProps` → empty → fetches prefill API → `t.promptParts = pf` (OVERWRITES)  
**Fix:** Deep merge instead of assignment. Prefill only fills empty fields, never overwrites existing data.

### Bug 3: Validate crashes on channel dicts
**File:** `server.py` line 1616  
**Sign:** Save button flashes "⏳ Saving..." then resets. No console error. Save-draft API never called.  
**Root:** `channels.get(c, "").strip()` — `channels.get('whatsapp')` returns a DICT (with sub-fields), not a string. `.strip()` on dict crashes. Validate returns `{status:"error"}` silently.  
**Fix:** `isinstance(channels.get(c), dict) and any((v or '').strip() for v in channels[c].values() if isinstance(v, str))`

### Bug 4: promptEditorStatus element missing from HTML
**File:** `prompt_builder_template.py`  
**Sign:** Save works (API, DB, localStorage all succeed) but user sees zero feedback  
**Root:** `document.getElementById('promptEditorStatus')` always returns null — element never existed in HTML  
**Fix:** Added `<span id="promptEditorStatus"></span>` inside a `.pb-status-bar` div below the header

### Bug 5: Server staleness (recurring)
**Sign:** Fixes committed and pushed but user still sees broken behavior  
**Root:** `pkill -f "venv/bin/python server.py"` kills BOTH the old server AND the shell running the restart command. The `nohup` never fires if the shell is killed mid-execution.  
**Fix:** Kill explicitly with `kill $(pgrep -f 'venv/bin/python server.py$')` — more specific pattern. Verify PID start time vs git commit time.

### Bug 6: API errors invisible to browser console  
**Sign:** No console errors, no network errors, but save fails  
**Root:** Server returns 200 HTTP with `{status:"error", contradictions:[...]}` body. The `.catch()` only fires on network errors. The `.then()` handler checks `data.status === 'ok'` and silently falls through when it's `'error'`.  
**Fix:** Add visible error indicator on the button itself ("✖ Error") when save fails, not just a status bar text.

## Verification Commands

### Check server freshness
```bash
echo "Server: $(ps -p $(pgrep -f 'venv/bin/python server.py$') -o lstart= 2>/dev/null)"
echo "Commit: $(cd /Users/greg/ara && git log -1 --format='%ai %s')"
```

### Test validate endpoint
```bash
curl -s -X POST http://localhost:8766/api/cadence/validate \
  -H "Content-Type: application/json" \
  -d '{"template_id":"cold","promptParts":{"brandPersonality":{"tone":"calm"},"channelSpecific":{"whatsapp":{"structure":"test"}}}}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('Status:', d.get('status'))"
```

### Test save-draft endpoint
```bash
curl -s -X POST http://localhost:8766/api/cadence/save-draft \
  -H "Content-Type: application/json" \
  -d '{"template_id":"cold","promptParts":{"brandPersonality":{"personality":"verify"}},"systemPrompt":"verify"}'
```

### Verify DB persistence
```python
from database import CadenceConfig, init_db
db = init_db()
cfg = db.query(CadenceConfig).filter(CadenceConfig.template_id == 'cold').first()
bp = cfg.config.get('promptParts', {}).get('brandPersonality', {}) if cfg else {}
print('Personality:', repr(bp.get('personality', '')))
db.close()
```

### Full browser verification (run in DevTools console)
```javascript
// Set value, click save, check status
document.querySelector('#pe_personality').value = 'verify-' + Date.now();
document.getElementById('pbSaveBtn').click();
setTimeout(() => {
  var st = document.getElementById('promptEditorStatus');
  var btn = document.getElementById('pbSaveBtn');
  console.log('Status:', st ? st.textContent : 'MISSING');
  console.log('Button:', btn ? btn.textContent : 'MISSING');
}, 3000);
```
