---
name: ara-prompt-builder-fixes
description: ARA prompt builder — client-side concatenation architecture, object field handling, validate (LLM) vs Final (no-LLM) separation, and overview chip state rendering.
---

# ARA Prompt Builder — Architecture & Fixes

## Architecture Overview

The prompt builder uses a **no-LLM-on-Final** architecture. The aggregated/Final tab is populated by client-side concatenation (`assembleSystemPrompt()`), not an LLM call. The LLM Validate button runs only the contradiction check — no compilation.

```
Prompt Parts (Brand → Sector → Security → Channels)
       │
       ▼
assembleSystemPrompt()  ← client-side, pure string concatenation
       │
       ├──▶ Final Tab (instant, no API call)
       └──▶ systemPrompt saved on Publish

Validate Button → POST /api/cadence/validate → LLM contradiction check only
                                                      │
                                                      ▼
                                             Shows warnings (advisory, not blocking)

Publish Button → POST /api/cadence/publish  → saves systemPrompt + promptParts
```

## Key Functions

### `assembleSystemPrompt(t)` (cadence_template.py ~line 2151)
Client-side concatenation that builds the system prompt from:
- Objective (from `t.objective`)
- Brand Voice (from `globalPromptParts.brandPersonality`)
- Sector Context (from `globalPromptParts.sectorSpecific` — includes valueProps, caseStudies, competition, pricing, FOMO)
- Security & Guardrails (from `globalPromptParts.security` — handles both string AND object)
- Channel Guidance (from `globalPromptParts.channelSpecific.whatsapp/email/call` — handles both string AND object)

**Used only as fallback.** The default behavior is to show the PUBLISHED prompt as-is.

### `openPromptEditor()` — Show Published Prompt, Not Re-Assembled

**Critical behavioral rule:** On open, the Final tab shows `t.systemPrompt` (last published) directly. It does NOT call `assembleSystemPrompt()`. Only falls back to assembly if no published prompt exists:

```javascript
function openPromptEditor() {
  var t = getTemplate();
  ...
  if (t.systemPrompt) {
    aggEl.textContent = t.systemPrompt;  // published prompt
  } else {
    assembleSystemPrompt(t);             // fallback
  }
  switchTab('brand');
}
```

This prevents the Final tab from showing a different version than what was published. The published prompt IS the source of truth — assembly only happens when there's nothing published yet or after user edits.

### `switchTab('aggregated')` — Same Rule
On tab switch, only re-assembles if no published prompt exists:
```javascript
if (t && !t.systemPrompt) assembleSystemPrompt(t);
```

### `savePromptAndClose()` — Saves Whatever Is in Final Tab
```javascript
var compiledPrompt = document.getElementById('aggregatedPrompt').textContent;
t.systemPrompt = compiledPrompt;
```
This means: if the Final tab shows the published prompt (no edits), it saves the same content. If constituents were changed and user switched to Final tab to see the assembled version, it saves the NEW assembled version. User must actively switch tabs and save to publish changes. **Auto-population on constituent change does not happen** — the user triggers the save explicitly.

### `collectPromptParts()` (cadence_template.py ~line 1935)
Gathers all prompt parts from the UI fields into a structured object for:
- Brand: tone, style, language, adaptLanguage, formality, vocabulary
- Sector: valueProps, caseStudies, competition, customers, pricing, fomo, deckRef
- Security: textarea string (serialized/deserialized to/from object in loadPromptParts)
- Channels: whatsapp, email, call textareas

### `loadPromptParts(t)` (cadence_template.py ~line 1860)
Populates the prompt builder fields from `globalPromptParts`. Handles **object deserialization**:
- Security object → formatted text with `## Injection Prevention`, `## Restricted Claims`, etc.
- WhatsApp object → `## Structure`, `## Tone`, `## Sequencing`
- Email object → `## Subject Strategy`, `## Body`, `## Sequencing`
- Call object → `## Intro`, `## Discovery Questions`, `## Objection Handling`, `## Booking`

## Critical: Object Field Handling (The [object Object] Bug)

**Symptom:** Compiled system prompt shows `[object Object]` for Security, WhatsApp, Email, and Call sections.

**Root cause:** `globalPromptParts.security` and `globalPromptParts.channelSpecific.whatsapp/email/call` are stored as **objects** (dictionaries) in the DB, but `assembleSystemPrompt()` was doing `'## Section\n' + global.security` — JavaScript concatenation of an object gives `[object Object]`.

**Fix:** Both `assembleSystemPrompt()` and `loadPromptParts()` must handle objects vs strings explicitly:

```javascript
// assembleSystemPrompt — security
var security = global.security;
if (security) {
  if (typeof security === 'string') {
    parts.push('## Security & Guardrails\n' + security);
  } else if (typeof security === 'object') {
    var secLines = [];
    if (security.injectionPrevention) secLines.push('Injection Prevention: ' + security.injectionPrevention);
    if (security.restrictedClaims) secLines.push('Restricted Claims: ' + security.restrictedClaims);
    if (security.escalation) secLines.push('Escalation Rules: ' + security.escalation);
    if (security.faqs) secLines.push('FAQs: ' + security.faqs);
    if (secLines.length) parts.push('## Security & Guardrails\n' + secLines.join('\n\n'));
  }
}

// assembleSystemPrompt — channels (same pattern)
['whatsapp', 'email', 'call'].forEach(function(ch) {
  var val = cs[ch];
  if (!val) return;
  if (typeof val === 'string') {
    parts.push('## ' + capitalize(ch) + '\n' + val);
  } else if (typeof val === 'object') {
    var chLines = [];
    for (var key in val) {
      if (val[key] && typeof val[key] === 'string') chLines.push(key + ': ' + val[key]);
    }
    if (chLines.length) parts.push('## ' + capitalize(ch) + '\n' + chLines.join('\n'));
  }
});
```

The same pattern applies in `loadPromptParts()` — serialize objects to formatted text for the textarea, and in `renderPromptOverview()` — check for object keys rather than assuming strings.

## ⚠️ `_skipAutoCompile` Flag Leaks Across Builder Sessions

**Symptom:** After publishing and reopening the builder, clicking the Final tab shows the placeholder text ("Compiling prompt…"). The prompt only appears after a manual page refresh.

**Root cause:** `publishPromptBuilder()` sets `window._skipAutoCompile = true` before calling `switchPbTab('final')` (line 1361). The `switchPbTab` function checks this flag and skips `compilePbPrompt()`. But the flag is NEVER cleared when `openPromptBuilder()` runs — it persists across builder open/close cycles.

Additionally, `pbContradictions` (the red issues/suggestions div shown after validation) is NEVER cleared on reopen. So the user sees stale validation errors from the previous publish session.

**Fix:** Reset all stale state at the top of `openPromptBuilder()`:

```javascript
function openPromptBuilder() {
  window.pbDirty = false;
  // Reset stale publish flags and validation state
  window._skipAutoCompile = false;
  document.getElementById('pbContradictions').innerHTML = '';
  document.getElementById('pbFinalPrompt').textContent = '';
  document.getElementById('pbContradictionsCount').textContent = '0';
  // ... rest of function
}
```

**Related:** The `window._skipAutoCompile = false` at the end of `switchPbTab()` (line 802) only applies to the NEXT tab switch within the same builder session. Once the builder is closed and reopened, the flag retains its last value.

**Rule:** Any one-shot state set during publish/validation that affects tab rendering must be cleared in `openPromptBuilder()`. Don't rely on tab-switch cleanup alone.

**The Final tab does NOT call the LLM.** It shows whatever `assembleSystemPrompt()` produces client-side. The `aggregatedPrompt` div defaults to "Loading published prompt..." and is populated immediately.

The old `/api/cadence/validate` endpoint had Task 2 (compile prompt) which was pure string concatenation sent to an LLM — burning tokens with no value. This was removed. The validate endpoint now only runs Task 1 (contradiction check).

**Old flow (removed):** Click Final → LLM call (20-30s) → wait → see compiled prompt
**Current flow:** Click Final → instant client-side concatenation → see compiled prompt

## ⚠️ Lazy-Loaded Tabs — DOM Textareas Don't Exist for Unvisited Tabs

**Critical pitfall.** The prompt builder's individual tabs (Brand, Sector, Security, WhatsApp, Email, Call) are lazy-loaded — only the currently active tab's textarea elements exist in the DOM at any time. This means:

- `document.getElementById('pe_emailBody')` returns `null` if the Email tab was never clicked
- `compilePbPrompt()` can't read from DOM textareas for tabs the user hasn't visited
- The old behavior (showing `t.systemPrompt` directly) avoided this issue entirely

**Fix in `compilePbPrompt()`:** For each section, first try the DOM textarea (`.pb-textarea` class), then fall back to traversing `getTemplate().promptParts`:

```javascript
for each section config:
  var domField = document.querySelector('#' + cfg.id + '.pb-textarea');
  var value = domField ? domField.value.trim() : '';
  if (!value && t) {
    // Navigate promptParts by the config's partPath (e.g. ['channelSpecific','email','body'])
    var obj = t;
    for (var j = 0; j < cfg.partPath.length; j++) {
      if (obj) obj = obj[cfg.partPath[j]];
    }
    value = (typeof obj === 'string' && obj.trim()) ? obj.trim() : '';
  }
  if (value) sections.push(value);
```

This gives the best of both worlds:
- Tabs the user has edited → reads live DOM value (real-time edits propagate)
- Tabs the user hasn't visited → reads from cached promptParts (has the published data)

**Check before assuming DOM exists:** Always use `querySelector('#' + id + '.pb-textarea')` (returns null if not found) rather than `document.getElementById(id)` (which can also return the wrong element from the sidebar — see Duplicate IDs).

## Validate → Publish Two-Step Flow

### Validate Button
- Calls `POST /api/cadence/validate` with prompt parts
- LLM checks for logical contradictions only (no compilation)
- Returns contradictions array
- Contradictions are **advisory, not blocking** — shown as orange warnings
- Diagnostics (token count, context %) computed from prompt parts, not compiled output

### Publish Button
- Saves the current client-assembled `systemPrompt` + `promptParts` to the DB via `POST /api/cadence/publish-global`
- Propagates to all three cadence templates (cold, inbound, nurture)
- Does NOT require passing the Validate step first
- Saves `promptParts` as structured data AND `systemPrompt` as the compiled text

## Overview Chip Grayscale Fix

**Symptom:** Brand, Sector, Security, WhatsApp, Email, Call chips show as gray/unfilled even though content exists.

**Root cause:** `renderPromptOverview()` was checking for specific fields that weren't populated:
- Brand: `phrases.length > 20` — but phrases is often empty when tone/style are filled
- Security: `injectionPrevention` — object key check on a potentially serialized string field
- Channels: `whatsapp.structure`, `email.subject`, `call.intro` — object key checks that fail when field is a flat string

**Fix:** Broadened checks to detect content in ANY relevant field:

```javascript
{ idx: 0, check: pp.brandPersonality && (
    (bp.tone && bp.tone !== 'warm') ||          // non-default tone
    (bp.phrases && bp.phrases.length > 10) ||    // custom phrases
    (bp.personality && bp.personality.length > 10)  // personality description
)},
{ idx: 2, check: pp.security && (
    (typeof pp.security === 'string' && pp.security.length > 10) ||
    (typeof pp.security === 'object' && (pp.security.injectionPrevention || pp.security.restrictedClaims))
)},
{ idx: 3, check: pp.channelSpecific && pp.channelSpecific.whatsapp && (
    (typeof wa === 'string' && wa.length > 10) ||
    (typeof wa === 'object' && (wa.structure || wa.tone || wa.sequencing))
)},
```

**Rule:** Always check `typeof val === 'string'` OR `typeof val === 'object'` with broad key coverage. Never assume a single field defines "filled" state.

## Critical: `globalPromptParts` Stale Cache Fix (Async Timing Bug)

**Symptom:** Prompt builder fields show stale/empty data even though server has correct published content. User sees 5 email sequences instead of 6, brand/personality looks different.

**Root cause:** The page load sequence is:
1. `loadData()` reads localStorage → populates `TEMPLATES` with potentially stale data
2. `renderCurrentTemplate()` → `migrateToGlobalPromptParts()` → copies `TEMPLATES[current].promptParts` to `globalPromptParts` **synchronously**
3. `fetchFromServer()` fires (async — hasn't returned yet)
4. User opens prompt builder → `loadPromptParts(t)` reads from `globalPromptParts` (stale data)
5. Later: `fetchFromServer()` returns → merges server data into `TEMPLATES` — but `globalPromptParts` is already cached and never refreshed

**Fix:** In the `fetchFromServer()` success handler, after detecting server data differs:
```javascript
if (changed) {
  // Reset and re-populate globalPromptParts with fresh server data
  globalPromptParts = null;
  migrateToGlobalPromptParts();
  ...
}
```

Also refresh the prompt builder fields if the editor is open when server data arrives:
```javascript
if (document.getElementById('promptEditorOverlay').classList.contains('open')) {
  var t = getTemplate();
  if (t) {
    loadPromptParts(t);
    var aggEl = document.getElementById('aggregatedPrompt');
    if (t.systemPrompt && aggEl) aggEl.textContent = t.systemPrompt;
  }
}
```

**Rule:** `globalPromptParts` is a **cache** that can go stale. Any async data load that changes `TEMPLATES` must also invalidate and repopulate `globalPromptParts`. The guard `if (globalPromptParts) return;` on `migrateToGlobalPromptParts` is the footgun — reset to `null` before re-calling.

## Backend: `/api/cadence/validate` Endpoint (server.py ~line 2210)

The validate endpoint now:
1. Resolves @-mentions in channel text
2. Sends prompt parts to LLM with ONLY the contradiction check task
3. Returns `{"contradictions": [...], "metrics": {...}}`
4. **No `compiled_prompt` in response** — removed entirely
5. Token metrics computed from `len(json.dumps(prompt_parts)) // 4`, not from compiled output

The endpoint prompt instructs the LLM to:
- Check for contradictions between components
- Respond ONLY with JSON: `{"contradictions": ["list", "of", "issues"]}`
- No compilation task, no output structure rules

## Backup/Restore: Single-Version Safety Net

Every publish to `POST /api/cadence/publish-global` now saves the previous system prompt before overwriting:

```python
existing.config["previous_systemPrompt"] = existing.config.get("systemPrompt", "")
existing.config["systemPrompt"] = compiled_prompt
```

**Restore by swap:** `POST /api/cadence/restore` toggles `systemPrompt` ↔ `previous_systemPrompt`:

```python
cfg["previous_systemPrompt"] = cfg.get("systemPrompt", "")
cfg["systemPrompt"] = prev
```

The Restore button (`↩ Restore Backup`) in the prompt builder footer calls the endpoint then refreshes UI via `fetchFromServer()`. Since it's a swap, clicking it twice restores forward. Only the immediately previous version is preserved — no version history.

**Full audit of all systemPrompt overwrite paths:** See `references/system-prompt-safety-audit.md`. Every endpoint and frontend caller that can modify systemPrompt, with blast radius and safeguards.

**Generate-prompt promptParts gap:** See `references/generate-prompt-promptparts-gap.md`. When regenerating systemPrompt, promptParts must also be rebuilt or the prompt builder tabs show stale content.

## ⚠️ Publish Endpoint Overwrites Config Instead of Merging

See `references/publish-config-overwrite.md` for full detail.

**Critical:** The `/api/cadence/publish` endpoint (`server.py` ~line 2090) originally did `existing.config = template` — replacing the entire config. Since the template sent from the frontend varies by caller, this caused silent data loss:

- **Main page `publishCadence()`** sends `template: t` — the **full template object** (steps, conditions, stopConditions, brandVoice, promptParts, systemPrompt, id, title, objective, etc.). The full merge loop below correctly preserves all of these.
- **Prompt builder `publishPromptBuilder()`** sends `template: { promptParts: parts, systemPrompt: compiled }` — a partial template with only 2 keys. The full merge loop correctly adds/updates these 2 and preserves everything else from existing config.

**Fix (June 2026 v2 — full merge loop):** Saves ALL template fields, not just specific ones:

```python
if existing:
    merged = dict(existing.config or {})
    for k, v in template.items():
        if v is not None and v != '':
            merged[k] = v
    existing.config = merged
    existing.updated_at = utcnow()
```

This replaces the earlier v1 fix (June 2026 v1) that only saved `promptParts`, `systemPrompt`, and `title` — which caused `steps`, `conditions`, and other metadata to be silently dropped on main-page publish.

**All three endpoints** (`/api/cadence/save-draft`, `/api/cadence/publish`, `/api/cadence/publish-global`) now use merge, not replace:
- **save-draft** — always used merge ✅
- **publish** — v1: specific-field merge (lost steps/conditions); v2: full merge loop (saves everything) ✅
- **publish-global** — iterates templates and updates individual fields (`cfg["promptParts"] = ...`) — verified: safe merge pattern ✅

**Lesson:** Every endpoint that writes to the JSON blob `CadenceConfig.config` must merge. The `for k, v in template.items()` pattern is the robust approach because it adapts to whatever the caller sends without hardcoding field names.

## Standardized Prompt Generation from Induction

**✅ BUILT.** See `references/induction-prompt-generation.md` for the full design.

A backend endpoint `POST /api/cadence/generate-prompt` in `server.py` auto-generates complete system prompts from induction docs. Section templates live in `prompt_templates.json` (project root). Ava triggers after induction.

Key architecture:
- Brand Voice, Security, & Channel anatomy inherited from `prompt_templates.json`
- Sector Context, Industry segments built from induction docs + tenant config
- Saves to all 3 templates (cold, inbound, nurture)
- Sequence evolution uses behavioral stages only — no time delays (those belong in the step selector)

## ⚠️ localStorage Cache Blinds the FE After DB Writes

**Critical pitfall.** After saving a new `systemPrompt` to the DB via `POST /api/cadence/publish-global` or `POST /api/cadence/generate-prompt`, the cadence page continues showing the OLD cached data from `localStorage['ara_cadence_data']`.

**Why:** The cadence page loads cached data from localStorage on page load, then fires `fetchFromServer()` asynchronously to get fresh data. `fetchFromServer()` updates in-memory `TEMPLATES` but the prompt builder's `compilePbPrompt()` may have already run before the fetch completes. Even after fetch completes, the `globalPromptParts` cache can go stale.

**Mitigation:**
1. Tell the user to **hard refresh** (`Cmd+Shift+R`) — clears browser cache and forces a fresh page load
2. Or clear localStorage programmatically: `localStorage.removeItem('ara_cadence_data')` followed by page reload
3. The generate-prompt endpoint's return includes a note about this
4. In `fetchFromServer()`, after updating TEMPLATES, call `saveData()` (updates localStorage) so subsequent loads get fresh data


## ⚠️ Duplicate IDs Across Template Files (The `#pe_valueProps` Bug)

**Critical pitfall.** Two files define elements with the same HTML `id`:
- `cadence_template.py` — the sidebar's Sector Intelligence fields use `class="sec-input"` with ids like `pe_valueProps`
- `prompt_builder_template.py` — the prompt builder textareas use `class="pb-textarea"` with the same ids

`document.getElementById('pe_valueProps')` returns whichever appears FIRST in the DOM (usually the sidebar `sec-input`, which is empty). The prompt builder's `.pb-textarea` version is never reached.

**Fix:** Always use `document.querySelector('#pe_valueProps.pb-textarea')` to target the prompt builder textarea specifically. Applied in both `setPbVal()` and `compilePbPrompt()`.

**Scope:** Applies to `pe_valueProps`, `pe_phrases`, `pe_personality`, `pe_injectionPrevention`, `pe_whatsappStructure`, `pe_emailBody`, `pe_callIntro` — any ID that exists in both files.

### `setPbVal()` Fix (prompt_builder_template.py)

The original function used `pb.querySelector('#' + id)` which hit the sidebar element first. Updated to prefer the `.pb-textarea` class:

```javascript
function setPbVal(id, val) {
  var pb = document.getElementById('pbOverlay');
  if (!pb) return;
  var el = pb.querySelector('#' + id + '.pb-textarea') || pb.querySelector('#' + id);
  // ... rest unchanged
}
```

### `compilePbPrompt()` Fix (prompt_builder_template.py)

The Final tab's concatenation function also needs `.pb-textarea` targeting:

```javascript
for (var i = 0; i < textareaIds.length; i++) {
  var field = document.querySelector('#' + textareaIds[i] + '.pb-textarea');
  // ... not document.getElementById(textareaIds[i])
}
```

## ⚠️ Main Page `publishCadence()` Called `publish-global` — Removed June 2026

**Critical bug discovered and fixed.** The Outreach Central page's `publishCadence()` function (in `cadence_template.py`, line 1604) was unconditionally calling `POST /api/cadence/publish-global` after every publish — broadcasting **cold** template's `promptParts` and `systemPrompt` to ALL three templates.

**The damage:** When cold's data was stale/truncated (due to the earlier config-overwrite bug), it overwrote inbound and nurture's correct prompts. Every step-timing edit the user made on the main page triggered this contamination.

**Fix:** Removed the entire `publish-global` call from `publishCadence()`. The `publish-global` endpoint is now only called from the prompt builder's `publishPromptBuilder()` (which is the correct caller — it intentionally shares prompt content across templates after the user explicitly validates and publishes prompt changes).

**Lesson:** `publish-global` is a prompt propagation mechanism, not a step-timing save mechanism. Never call it from the main page's publish flow.

## compilePbPrompt systemPrompt Fallback for Sections Without Textareas (June 2026)

### The Problem

`compilePbPrompt()` reads from 6 primary DOM textareas (Brand, Sector, Security, WhatsApp, Email, Call) and falls back to promptParts for unvisited tabs. But sections 7-12 (Lead Context Awareness, Industry Contextualization, FOMO & Curiosity, Message Structure Principles, Sequence Evolution Logic, Important Communication Rules) plus Objective don't have dedicated textareas. The original code tried to build them from `collectPbParts()` sub-fields (`parts.leadContext.value`, `parts.sectorSpecific.caseStudies`, `parts.brandPersonality.personality`, etc.) which were empty after the promptParts regeneration.

### The Fix

After building the 6 primary sections, check `t.systemPrompt` for any missing sections by heading match:

```javascript
// ── Fill any missing sections from t.systemPrompt ──
var t2 = getTemplate();
if (t2 && t2.systemPrompt && sections.length > 0) {
  var wanted = [
    'Objective',           // goes FIRST in the final output
    'Lead Context Awareness',
    'Industry Contextualization',
    'FOMO & Curiosity',
    'Message Structure Principles',
    'Sequence Evolution Logic',
    'Important Communication Rules'
  ];
  // Check which ones we already have
  var have = {};
  sections.forEach(function(s) {
    var fl = s.trim().split('\n')[0];
    wanted.forEach(function(w) { if (fl.indexOf(w) >= 0) have[w] = true; });
  });
  // Extract from systemPrompt (split by \n\n---\n\n)
  var sysParts = t2.systemPrompt.split('\n\n---\n\n');
  sysParts.forEach(function(sp) {
    sp = sp.trim();
    var fl = sp.split('\n')[0].replace(/^#+\s*/, '').trim();
    wanted.forEach(function(w) {
      if (!have[w] && fl.indexOf(w) >= 0 && sp.length > 100) {
        if (w === 'Objective') sections.unshift(sp);  // first
        else sections.push(sp);
        have[w] = true;
      }
    });
  });
}
```

**Key details:**
- `Objective` goes first via `unshift()`, all others via `push()`
- Checks by heading text match (e.g., "## Lead Context Awareness" matches `fl.indexOf('Lead Context Awareness')`)
- Requires `sp.length > 100` to avoid empty/placeholder matches
- Only fills sections NOT already covered by the 6 primary textareas or the collectPbParts() path

### Edge Cases

- If a section exists in BOTH textarea/promptParts AND systemPrompt, the textarea/promptParts version takes priority (it was already pushed before the fallback runs)
- If `t.systemPrompt` separator differs (e.g., `---` vs `\n\n---\n\n`), the split may not match. Verify the actual separator used in the stored prompt.
- Objective: `unshift()` ensures it's first regardless of where it appears in systemPrompt

## ⚠️ Email Section Content Separation — Subject vs Body (June 2026)

**Critical architecture fact.** The Email section in `prompt_templates.json` (8,631 chars) contains BOTH subject lines AND body/sequencing, because both are needed in the system prompt for the LLM. But the prompt builder has TWO SEPARATE tabs: Subject Lines (`pe_emailSubject`) and Body (`pe_emailBody`), backed by TWO SEPARATE fields in `promptParts`:

```
prompt_templates.json["Email"]
  │
  ├── Subject Lines section (1,656 chars)  →  promptParts.email.subject  →  pe_emailSubject tab
  │
  └── Body + Sequencing section (6,973 chars) →  promptParts.email.body  →  pe_emailBody tab
```

**When editing the Email section, this means:**
- The subject lines subsection MUST be in `prompt_templates.json["Email"]` (for the system prompt / LLM)
- But it MUST NOT be in `promptParts.email.body` (the prompt builder Body tab — subject lines have their own tab)
- The body/sequencing content goes into BOTH `prompt_templates.json["Email"]` AND `promptParts.email.body`

**If you copy the full `prompt_templates.json["Email"]` into `email.body`, you'll duplicate the subject lines into the Body tab.** The user will see subject line rules in the Email Body textarea.

**Correct sync pattern:** Extract only the content after `### Body & Sequence Rules` for `email.body`. The subject headers (`### Subject Lines`) stay in `prompt_templates.json` but never go into `promptParts.email.body`.

See `references/email-section-content-mapping.md` for the complete update flow.

## ⚠️ Generate-Prompt: `---` Separator Splits Section Content (June 2026)

**Symptom:** After calling `POST /api/cadence/generate-prompt`, the Email section appears broken into multiple pieces in the compiled system prompt (8 separate sections instead of 1 contiguous block).

**Root cause:** The generate-prompt function splits sections using `full_prompt.split('---')`. If any section text CONTAINS `---` (e.g., email sequence with `---` divider between EMAIL 1 → EMAIL 2 → EMAIL 3), the split produces false section boundaries.

**Impact:** The LLM still receives the full content (all text is present, just spread across sections), so behavior is unaffected. But the `sections` array in the generate-prompt response shows inflated counts, and any code that iterates `sections` by index may break.

**Fix (recommended):** Use a safer separator in the section text. Replace `---` dividers within the Email section with e.g. `___` or `---` with surrounding context that prevents accidental matches. Or change the generate-prompt split pattern to `\n\n---\n\n` (with newlines) — but this requires content to also respect the newline constraint.

**Current workaround:** No functional impact. The section text is delivered to the LLM in its entirety regardless of split boundaries.

**Lesson:** When inserting content into any section of `prompt_templates.json` that uses `---` as a divider, verify the separator doesn't appear within the content. The user's email sequence explicitly uses `---` between EMAIL 1-5, which creates false section breaks in the generated prompt.

## ⚠️ Generate-Prompt: promptParts NOT Updated After Regeneration (June 2026)

**Symptom:** After running `POST /api/cadence/generate-prompt`, the prompt builder tabs show the OLD section content even though the system prompt was updated with new template text.

**Root cause:** The `generate_system_prompt()` function previously tried to call an undefined helper `_build_prompt_parts_from_sections()` to rebuild promptParts. This was fixed to preserve existing promptParts:

```python
# Before (broken — June 2026):
new_pp = _build_prompt_parts_from_sections(sections, tenant_name, segments)
existing.config["promptParts"] = new_pp  # NameError: function doesn't exist

# After (fixed):
existing.config["promptParts"] = existing.config.get("promptParts", {})
# Keeps existing promptParts — preserve the data already in DB
```

**Consequence:** `generate-prompt` now **only** updates `systemPrompt`. It does NOT update `promptParts`. This means:
- The LLM reads updated content from systemPrompt ✅
- The prompt builder tabs show the OLD content from promptParts ❌
- The user sees a mismatch between tabs and Final tab after generate-prompt

**Fix when this matters:** Run a manual sync script that updates `promptParts` from the updated `prompt_templates.json` (see `references/email-section-content-mapping.md` for the exact SQL pattern).

**Lesson:** Regenerating systemPrompt via `generate-prompt` is a one-sided operation — it only refreshes what the LLM sees, not what the prompt builder UI shows. For full sync, update promptParts separately.

## CompilePbPrompt Behavior Change (June 2026)

The `compilePbPrompt()` function was changed from:
1. **Old:** Show `t.systemPrompt` (cached published version) directly — edits in individual tabs never reached the Final tab
2. **New:** Read from each tab's `.pb-textarea` DOM element, then concatenate with `---` separators. Only falls back to `t.systemPrompt` if all DOM fields are empty.

This means edits in individual tabs ARE reflected in the Final tab immediately (on next `compilePbPrompt()` call). The Final tab is now a true amalgamation of all individual sections, not a snapshot from the last publish.

The 11-section order is: Brand Voice → Sector Context → Security & Guardrails → WhatsApp → Email → Call → Industry Contextualization → FOMO & Curiosity → Message Structure Principles → Sequence Evolution Logic → Important Communication Rules.

### 1. Missing `sourceTag` variable
**Fix:** Add `var sourceTag = ...` in the `decks.forEach(function(d)` loop.

### 2. Tab click blocked by `final` CSS class
**Fix:** Use `dataset.tab` instead of `classList.contains('final')`.

### 3. Duplicated controls (Security working hours in builder vs cadence)
**Fix:** Remove the prompt builder duplicate.

### 4. Sequencing tab removal
**Fix:** Remove sequencing tab HTML/CSS/JS references.

### 5. ❌ Old: Auto-compile recursive loop
**Old symptom:** `switchPbTab('final')` in `validateAndCompilePrompt()` success handler created infinite loop.
**Current status:** Superseded — Final tab has no auto-compile at all.

### 6. ✅ Security token count showing 1 tok
**Fix:** Changed `len(prompt_parts.get("security", "")) // 4` to `len(json.dumps(prompt_parts.get("security", {}))) // 4`. Dictionary field used `len(dict)` (returns key count) instead of `json.dumps()`.

### 7. ❌ Old: Publish blocked by contradictions
**Current status:** Contradictions are now advisory only — publish works regardless.

### 8. ❌ Old: Validate Compilation Waste (Pre-June 2026)
**Current status:** Zero LLM calls on Final tab. Client-side `assembleSystemPrompt()` handles all concatenation. Validate endpoint's Task 2 removed entirely.

## Deployment
- `prompt_builder_template.py` is imported by `cadence_template.py` at module level
- `cadence_template.py` is imported by `server.py` at module level
- Both require server restart to pick up changes
- **Hard refresh needed** (Cmd+Shift+R) after template changes — browser caches HTML aggressively

## ⚠️ TWO PROMPT BUILDERS EXIST — Critical Architecture Fact

The ARA codebase has **two separate prompt builder UIs**, each in its own file:

| Builder | File | Overlay ID | Trigger | Functions |
|---------|------|-----------|---------|-----------|
| **Old modal** | `cadence_template.py` (~line 797) | `promptEditorOverlay` | `openPromptEditor()` | `assembleSystemPrompt()`, `loadPromptParts()`, `savePromptAndClose()` |
| **New slide-over** | `prompt_builder_template.py` | `pbOverlay` | `openPromptBuilder()` (called from the ✎ Open Builder button) | `compilePbPrompt()`, `collectPbParts()`, `savePromptBuilder()`, `publishPromptBuilder()` |

**The button at line 746 of `cadence_template.py` calls `openPromptBuilder()` — which is defined in `prompt_builder_template.py`, NOT `cadence_template.py`.** The old `promptEditorOverlay` (`openPromptEditor()`) may be deprecated or reachable via direct URL only.

**THIS IS THE #1 SOURCE OF BUGS when fixing the prompt builder.** If you edit the wrong file, you'll see no changes in the UI because the user interacts with the OTHER builder.

### How to tell which builder is being used

Open the prompt builder. Look at the UI:
- **Old modal** (cadence_template.py): Centered modal, tab-based with `prompt-editor-tab`, `prompt-editor-body`, architecture bar with numbered steps, "Validate" + "Save & Close" buttons at bottom
- **New slide-over** (prompt_builder_template.py): Full-screen slide-over panel from right with BACKDROP BLUR, left sidebar nav (Brand & Personality, Sector Intelligence, Security, WhatsApp, Email, Voice Call), main workspace with architecture bar at top, "Save Changes" and "Publish" buttons in top-right header

### What NOT to do

- ❌ Editing `cadence_template.py`'s prompt editor when the user is using `prompt_builder_template.py` (and vice versa)
- ❌ Assuming there's only one prompt builder
- ❌ Grepping only within one file — always `grep -rn` across the whole project
- ❌ Only testing changes against one builder

### How to systematically find all surfaces

```bash
# Find all template files that could have a prompt builder
grep -rn "prompt.*overlay\|pbOverlay\|promptEditorOverlay\|openPrompt\|PromptBuilder" /Users/greg/ara/*.py
```

This revealed THREE files: `cadence_template.py`, `prompt_builder_template.py`, `prompt_editor_mod.py`. Always check all before declaring a fix complete.

## Final Tab Auto-Compile Bug Across Both Builders

Both builders had the SAME bug: switching to the Final tab triggered an LLM call (`POST /api/cadence/validate`) that expected a `compiled_prompt` in the response. When the backend removed `compiled_prompt` (to save tokens), both builders showed "No prompt generated" on the Final tab.

### Old Builder Fix (`cadence_template.py`)
- `switchTab()` changed from `assembleSystemPrompt(t)` (unconditional) to `if (t && !t.systemPrompt) assembleSystemPrompt(t)` — only assembles if nothing published
- `openPromptEditor()` shows `t.systemPrompt` (published) instead of re-assembling

### New Builder Fix (`prompt_builder_template.py`)
- `switchPbTab()` changed from `validateAndCompilePrompt()` (LLM call) to `compilePbPrompt()` (client-side concatenation)
- `validateAndCompilePrompt()` no longer sets the Final tab content — only shows contradictions and stats

### Key Lesson
**Never assume a fix in one builder propagates to the other.** Both builder files have independent implementations with different function names, different data flow, and different UI frameworks. A fix in `cadence_template.py`'s `switchTab()` has ZERO effect on `prompt_builder_template.py`'s `switchPbTab()`.

### New Builder: `compilePbPrompt()` (prompt_builder_template.py ~line 967)

Client-side concatenation for the new slide-over prompt builder.
**Reads from DOM textareas first, falls back to promptParts.** This is a June 2026 change from the previous behavior which showed `t.systemPrompt` (stale published version) directly.

```javascript
function compilePbPrompt() {
  var sections = [];
  
  // Try DOM textareas first (real-time edits), fall back to promptParts for unvisited tabs
  // This matters because tabs are lazy-loaded — only the active tab's textareas exist in DOM.
  var sectionConfigs = [
    { id: 'pe_phrases',              partPath: ['promptParts','brandPersonality','phrases'] },
    { id: 'pe_valueProps',           partPath: ['promptParts','sectorSpecific','valueProps'] },
    { id: 'pe_injectionPrevention',  partPath: ['promptParts','security','injectionPrevention'] },
    { id: 'pe_whatsappStructure',    partPath: ['promptParts','channelSpecific','whatsapp','structure'] },
    { id: 'pe_emailBody',            partPath: ['promptParts','channelSpecific','email','body'] },
    { id: 'pe_callIntro',            partPath: ['promptParts','channelSpecific','call','intro'] },
  ];
  
  var t = getTemplate();
  for each config:
    - Try document.querySelector('#' + cfg.id + '.pb-textarea') for real-time DOM value
    - If empty, traverse t[partPath] for promptParts fallback
    - For email (pe_emailBody): also read pe_emailSubject, prepend as "## Email — Subject Lines"
  
  // Build remaining 5 sections from collectPbParts() data:
  // Industry Contextualization, FOMO, Message Structure, Sequence Evolution, Communication Rules
  
  el.textContent = sections.join('\n\n---\n\n');
}
```

**Behavior:**
- Sources of truth, in order: (1) DOM textarea value (real-time edit), (2) promptParts from `getTemplate()` (cached), (3) empty
- Edits in individual tabs ARE reflected in the Final tab immediately on next `compilePbPrompt()` call
- Lazy-loaded tabs that haven't been visited fall back to promptParts data
- This is a CHANGE from the previous behavior where `t.systemPrompt` was shown directly and edits never propagated

**Critical implementation details:**
- Uses `.pb-textarea` class selector to avoid duplicate-ID conflicts (see `⚠️ Duplicate IDs` section)
- Always includes `pe_emailSubject` as a separate "## Email — Subject Lines" section before the email body
- Each section is separated by `---` in the final output
- Order: Brand → Sector → Security → WhatsApp → Email-Subject → Email-Body → Call → Industry → FOMO → Message-Structure → Sequence-Evolution → Communication-Rules

### The Validate Button (new builder)
The `validateAndCompilePrompt()` function still exists but is no longer auto-triggered. It's called when the user clicks a "Validate" button (line 58 shows `pbSaveBtn` and `Publish`). It:
1. Calls `POST /api/cadence/validate` (LLM contradiction check only)
2. Shows contradictions in `pbContradictions` container
3. Updates live stats via `updateLiveStats(data)`
4. Does NOT touch `pbFinalPrompt` content (that stays from `compilePbPrompt()`)

### The Publish Button (new builder)
The `publishPromptBuilder()` function:
1. Collects prompt parts via `collectPbParts()`
2. Concatenates client-side (same as `compilePbPrompt()`)
3. Saves `systemPrompt` + `promptParts` to all templates via `POST /api/cadence/publish-global`
4. Closes the builder
