# Prompt Builder Debugging & Prefill Patterns

## Duplicate ID Conflict (Critical)

The cadence page renders **two Prompt Builder instances** simultaneously on the same DOM:

| Builder | File | Overlay ID | Field Class | Position in DOM |
|---------|------|-----------|-------------|-----------------|
| Inline | `cadence_template.py` | `promptEditorOverlay` | `sec-input` | First (earlier in HTML) |
| Full-screen | `prompt_builder_template.py` | `pbOverlay` | `pb-textarea` | Second (appended at end) |

**Both use identical field IDs** (`pe_valueProps`, `pe_caseStudies`, `pe_style`, `pe_phrases`, etc.). This means:

- `document.getElementById('pe_valueProps')` → **always returns the inline builder's element** (first in DOM)
- `document.querySelector('#pe_valueProps')` → **also returns the first match only**
- `document.querySelectorAll('#pe_valueProps')` → returns both; index `[0]` = inline (hidden), index `[1]` = full-screen (visible)

**Consequence:** `setVal()` and `gv()` always hit the hidden inline builder's fields. The visible full-screen builder's fields stay empty — the user sees placeholder text only.

### Fix Pattern

Scope all DOM queries to the visible overlay using `#pbOverlay` container:

```javascript
var pb = document.getElementById('pbOverlay');

function setPbVal(id, val) {
  var el = pb.querySelector('#' + id);
  if (el) {
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') {
      el.value = val != null ? val : '';
    } else {
      el.textContent = val != null ? val : '';
    }
  }
}

function gvPbVal(id) {
  var el = pb.querySelector('#' + id);
  return el ? el.value : '';
}
```

**Apply to all functions in `prompt_builder_template.py` that read or write field values:**
- `applyPbData()` — replace all `setVal()` → `setPbVal()`, scope `document.querySelector()` → `pb.querySelector()`
- `collectPbParts()` — replace all `gv()` → `gvPbVal()`, scope `document.querySelector()` → `pb.querySelector()`
- Tone chips, language chips, workingHours/weekdays checkboxes — all must use `pb.querySelector()`

### Debugging Checklist

When a field appears blank but you've verified the value is set:

1. `document.querySelectorAll('#' + id).length` — are there duplicates?
2. `document.getElementById(id).className` — is it `sec-input` (inline, hidden) or `pb-textarea` (full-screen, visible)?
3. Check the second element: `document.querySelectorAll('#' + id)[1].value`
4. Check which overlay is open: `document.getElementById('pbOverlay').classList.contains('open')`

## Prefill API — Object Serialization

The prefill API returns structured objects for some fields:

```json
{
  "security": {
    "injectionPrevention": "...",
    "restrictedClaims": "...",
    "escalation": "...",
    "faqs": "..."
  },
  "channelSpecific": {
    "whatsapp": { "structure": "...", "tone": "...", "sequencing": "..." },
    "email": { "subject": "...", "body": "...", "sequencing": "..." },
    "call": { "intro": "...", "discovery": "...", "objections": "...", "booking": "..." }
  }
}
```

But the form textareas expect **flat strings**. Setting `el.value = object` produces `"[object Object]"` (15 chars).

**Fix:** Serialize the object into formatted text before setting the value:

```javascript
// Security — serialize object
var sec = pp.security || {};
if (typeof sec === 'object') {
  var parts = [];
  if (sec.injectionPrevention) parts.push('## Injection Prevention\n' + sec.injectionPrevention);
  if (sec.restrictedClaims) parts.push('## Restricted Claims\n' + sec.restrictedClaims);
  if (sec.escalation) parts.push('## Escalation\n' + sec.escalation);
  if (sec.faqs) parts.push('## FAQs\n' + sec.faqs);
  setVal('pe_security', parts.join('\n\n'));
}

// WhatsApp — combine structure/tone/sequencing
var wa = cs.whatsapp || {};
if (typeof wa === 'object' && wa.structure) {
  var waParts = ['Structure: ' + wa.structure];
  if (wa.tone) waParts.push('Tone: ' + wa.tone);
  if (wa.sequencing) waParts.push('Sequencing: ' + wa.sequencing);
  setVal('pe_whatsapp', waParts.join('\n'));
}
```

## Prefill Guard Logic

The prefill guard determines whether to call the induction prefill API. **Must check for the specific missing data, not a proxy field:**

```javascript
// WRONG — brandPersonality exists but sector data is empty
if (globalPromptParts && globalPromptParts.brandPersonality) return;

// RIGHT — check the specific field that might be empty
if (globalPromptParts && globalPromptParts.sectorSpecific &&
    globalPromptParts.sectorSpecific.valueProps) return;
```

**Applies to both builders:**
- `cadence_template.py`: `prefillFromInduction()` checks `globalPromptParts.sectorSpecific?.valueProps`
- `prompt_builder_template.py`: `loadPromptBuilderData()` checks `t.promptParts?.sectorSpecific?.valueProps`

## Three Template Files

Changes to the Prompt Builder must propagate across ALL three files:

| File | Role | Builder Type | Key Functions |
|------|------|-------------|---------------|
| `cadence_template.py` | Main page | Inline overlay | `prefillFromInduction()`, `loadPromptParts()`, `migrateToGlobalPromptParts()`, `assembleSystemPrompt()` |
| `prompt_builder_template.py` | Full-screen slide-over | Full-screen | `loadPromptBuilderData()`, `applyPbData()`, `collectPbParts()`, `openPromptBuilder()` |
| `prompt_editor_mod.py` | Alt inline (may be dead) | Inline | `prefillFromInduction()`, `loadPromptParts()` |

**Always grep across ALL three when:**
- Adding/removing a tab
- Changing field IDs
- Updating prefill logic
- Modifying load/save/collect functions

The files are imported as Python string variables: `cadence_template.py` → `CADENCE_HTML`, which imports `PROMPT_BUILDER_HTML` from `prompt_builder_template.py`. `prompt_editor_mod.py` is NOT imported by the server (dead file as of May 2026).

## Prefill Deep Merge Pattern (May 2026)

When `loadPromptBuilderData()` fetches the induction prefill API, the response must NOT overwrite existing saved data. **Bug scenario:** user saves brand personality → refreshes page → prefill API fires → `t.promptParts = pf` overwrites the saved data → applied prompt has no personality.

**The fix:** Before applying prefill data, deep merge — only fill fields that are empty or missing:

```javascript
// BEFORE — OVERWRITES all saved data:
if (data.prefill && data.prefill[t.id]) {
  t.promptParts = data.prefill[t.id];
  applyPbData(t.promptParts, {});
}

// AFTER — deep merge, only fills empty fields:
if (data.prefill && data.prefill[t.id]) {
  t.promptParts = t.promptParts || {};
  var pf = data.prefill[t.id];
  for (var section in pf) {
    if (!pf.hasOwnProperty(section)) continue;
    if (typeof pf[section] === 'object' && !Array.isArray(pf[section])) {
      t.promptParts[section] = t.promptParts[section] || {};
      for (var field in pf[section]) {
        if (!pf[section].hasOwnProperty(field)) continue;
        if (!t.promptParts[section][field] || t.promptParts[section][field] === '') {
          t.promptParts[section][field] = pf[section][field];
        }
      }
    } else if (!t.promptParts[section]) {
      t.promptParts[section] = pf[section];
    }
  }
  applyPbData(t.promptParts, {});
}
```

**Root cause chain:**
1. User saves → `t.promptParts` written to localStorage via `saveCurrentState()`
2. Page refresh → `loadData()` reads from localStorage → `t.promptParts` has saved data
3. `loadPromptBuilderData()` checks `sectorSpecific.valueProps` — empty (user only filled Brand)
4. Prefill fires → overwrites `t.promptParts = pf` → saved data lost
5. `applyPbData(pf, {})` renders prefill → no saved personality

**Symptom:** "Save doesn't work" — user saves, refreshes, field is back to default. The API is not failing; it's succeeding too enthusiastically.

**Verification:**
1. Type "Witty" in personality field, click Save Changes
2. Refresh page (Cmd+R)
3. Re-open the builder
4. `document.querySelector('#pe_personality').value` should show "Witty", not the prefill default

## Async Prefill Timing

The prefill fetch is async. If the user opens the builder before the fetch completes, fields show placeholder text briefly. The fetch typically completes in <500ms.

**Pattern:** The prefill fires on page load (from `renderCurrentTemplate()`) and stores data in `globalPromptParts`. When the builder opens, `loadPromptParts()` reads from `globalPromptParts` — no async delay on open. The full-screen builder has its own async prefill in `loadPromptBuilderData()`, which sets values in the `.then()` callback.

## Input Value vs Placeholder

When debugging "blank" fields:
- `el.value` — the actual value (empty string = blank)
- `el.placeholder` — the lighter grey hint text
- `el.value === el.placeholder` — true if the value IS the placeholder text (shouldn't happen)
- CSS: `color:#111` for value, `color:#9A9A9E` for placeholder (`.pb-textarea::placeholder`)
