# Publish → Reopen → Blank Final Tab Bug

## Timing Diagram

```
User clicks Publish
  │
  ▼
publishPromptBuilder()
  │  POST /api/cadence/validate
  │  │
  │  ▼ (contradictions found)
  │  window._skipAutoCompile = true
  │  switchPbTab('final')     ← compilePbPrompt() SKIPPED (flag is true)
  │  window._skipAutoCompile = false  ← resets for NEXT tab switch
  │  │
  │  POST /api/cadence/publish
  │  │
  │  ▼
  │  saveCurrentState()      ← saves to localStorage
  │  closePromptBuilder()    ← overlay hides, _skipAutoCompile stays false
  │  loadTemplates()         ← re-renders page
  │
  ▼
User clicks Open Builder
  │
  ▼
openPromptBuilder()
  │  loadPromptBuilderData()
  │  │  applyPbData()  ← populates textareas
  │
  ▼
User clicks Final tab
  │
  ▼
switchPbTab('final')
  │  _skipAutoCompile is false  ✓ compilePbPrompt() SHOULD run
  │  BUT: Final tab already shows placeholder from HTML default
  │  AND: pbContradictions still has old red validation text
```

## Root Causes

1. **`_skipAutoCompile`** — Set during publish validation, not reset on builder reopen. Fixed in `openPromptBuilder()`.

2. **Stale contradictions** — `pbContradictions.innerHTML` is never cleared. Persists across opens. Fixed in `openPromptBuilder()`.

3. **Stale Final tab text** — `pbFinalPrompt.textContent` shows placeholder from HTML default. Should be cleared on open so the next compile shows fresh content.

## The Fix (Single Location)

All three issues are fixed in `openPromptBuilder()`:

```javascript
function openPromptBuilder() {
  window.pbDirty = false;
  window._skipAutoCompile = false;                     // Fix 1
  document.getElementById('pbContradictions').innerHTML = '';  // Fix 2
  document.getElementById('pbFinalPrompt').textContent = '';   // Fix 3
  document.getElementById('pbContradictionsCount').textContent = '0';
  // ... rest unchanged
}
```

## Why Refresh Works

Reloading the page (`Cmd+R` / `location.reload()`):
- Clears all in-memory JS state (including `_skipAutoCompile`)
- Re-runs `loadData()` → `loadTemplates()` from localStorage (fresh publish data)
- Re-runs `fetchFromServer()` → updates TEMPLATES
- When user opens builder and clicks Final tab, `_skipAutoCompile` is properly undefined/false
