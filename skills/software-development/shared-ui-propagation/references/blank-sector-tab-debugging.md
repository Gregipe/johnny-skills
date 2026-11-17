# Blank / Empty Prompt Builder Section — Debugging (May 2026)

When a Prompt Builder section (Sector, Security, or any channel tab) appears blank despite prefill data existing, check these failure modes in order.

## Failure 1: Object-to-String Serialization

**Symptoms:** Fields show `[object Object]` (exactly 15 chars). `el.value.length === 15`.

**Root cause:** The prefill API returns structured objects (e.g. `{injectionPrevention: "...", restrictedClaims: "..."}`) but the frontend load function does `setVal('pe_security', pp.security || '')`. Setting `el.value = {object}` produces the string `"[object Object]"`.

**Fix:** Serialize the object to flat text before setting:

```javascript
// DON'T: setVal('pe_security', pp.security || '');

// DO:
var sec = pp.security || {};
if (typeof sec === 'object') {
  var parts = [];
  if (sec.injectionPrevention) parts.push('## Injection Prevention\n' + sec.injectionPrevention);
  if (sec.restrictedClaims) parts.push('## Restricted Claims\n' + sec.restrictedClaims);
  if (sec.escalation) parts.push('## Escalation\n' + sec.escalation);
  if (sec.faqs) parts.push('## FAQs\n' + sec.faqs);
  setVal('pe_security', parts.join('\n\n'));
} else {
  setVal('pe_security', sec || '');
}
```

Same pattern applies to channel prompts (`cs.whatsapp`, `cs.email`, `cs.call`) which are also objects with `.structure`, `.tone`, `.sequencing` etc.

**Check:**
```javascript
document.getElementById('pe_security').value.length // 15 → Failure 1
```

## Failure 2: Collapsed Cards With No Input Elements

**Symptoms:** Sector tab shows card headers (Value Proposition, Case Studies, etc.) but only Value Proposition has content. Other cards show a `+` toggle and no textarea at all.

**Root cause:** `prompt_builder_template.py` uses a collapsible card grid where `pb-mod-card` elements without the `expanded` class only render a header (title + `+` toggle) — no `card-body` div, no textarea.

**Fix (two parts):**
1. Add `expanded` class to each collapsed card
2. Add `<textarea>` elements inside each card-body

```html
<!-- BEFORE — collapsed, no body -->
<div class="pb-mod-card">
  <div class="pb-mod-card-header">
    <span class="pb-mod-card-title">Case Studies</span>
    <button class="pb-mod-toggle">+</button>
  </div>
</div>

<!-- AFTER — expanded, has body -->
<div class="pb-mod-card expanded">
  <div class="pb-mod-card-header">
    <span class="pb-mod-card-title">Case Studies</span>
    <button class="pb-mod-toggle">−</button>
  </div>
  <div class="pb-mod-card-body">
    <textarea class="pb-textarea" id="pe_caseStudies"></textarea>
  </div>
</div>
```

## Failure 3: Missing Load/Collect Functions

After adding textareas, also update:
- `applyPbData()` — add `setVal('pe_fieldName', data.fieldName || '')` for each new field
- `collectPbData()` — add `fieldName: gv('pe_fieldName')` in the `sectorSpecific` block

**Check:**
```javascript
var fields = ['pe_valueProps','pe_caseStudies','pe_competition','pe_customers','pe_pricing','pe_fomo','pe_deckRef'];
var out = {};
fields.forEach(function(id) {
  var el = document.getElementById(id);
  out[id] = el ? (el.value ? el.value.length + ' chars' : 'EMPTY') : 'MISSING';
});
JSON.stringify(out);
// Any field showing 'MISSING' means the HTML element doesn't exist
// Any '0 chars' means the load function isn't filling it
```

## Failure 4: Prefill Guard Blocking (Hardest to Spot)

**Symptoms:** Fields have content when tested fresh (after clearing localStorage or hard refresh), but show empty on normal page load because the prefill API call never fires.

**Root cause:** The prefill guard checks for existence of `brandPersonality` (or another unrelated field) as a proxy for "already has data." If migration (or a previous session) populated `globalPromptParts` with `brandPersonality` but left `sectorSpecific` empty, the guard returns early and NO prefill data is fetched.

```javascript
// BROKEN — blocks prefill if ANY brand data exists
if (globalPromptParts && globalPromptParts.brandPersonality) return; // BUG: sector could be empty!

// FIXED — checks the specific section that might be empty
if (globalPromptParts && globalPromptParts.sectorSpecific && globalPromptParts.sectorSpecific.valueProps) return;
```

**When to suspect:** Opening the builder shows brand/phrases/selections populated (from migration) but sector/security/channels are empty or show `[object Object]`.

**Where to check (two locations):**
1. `cadence_template.py` → `prefillFromInduction()` guard at ~line 2052
2. `prompt_builder_template.py` → `loadPromptBuilderData()` guard at ~line 798

**Fix:** Change the guard condition to check whether the SPECIFIC section you want to prefill has actual content — not whether any section exists. Use a field that the prefill populates (like `valueProps` for sector data, `injectionPrevention` for security, or `structure` for channel prompts).

```javascript
// Sector: check valueProps exists
if (globalPromptParts?.sectorSpecific?.valueProps) return;

// Security: check injectionPrevention exists
if (globalPromptParts?.security?.injectionPrevention) return;

// Channels: check structure exists
if (globalPromptParts?.channelSpecific?.whatsapp?.structure) return;
```

The same pattern applies in `prompt_builder_template.py` where the guard checks `pp` (from `t.promptParts`) and `cache` (from `promptPartsCache`):

```javascript
// BROKEN
if (!pp.brandPersonality && !cache.brandPersonality) { fetch(...) }

// FIXED
if (!(pp.sectorSpecific?.valueProps) && !(cache.sectorSpecific?.valueProps)) { fetch(...) }
```

## Failure 5: Duplicate Element IDs Across Components

**Symptoms:** `document.getElementById('pe_valueProps')` returns an element with content (619 chars), but the VISIBLE textarea on screen shows placeholder text only. Using `querySelectorAll('#pe_valueProps')` shows 2+ elements with different classes.

**Root cause:** Two separate overlays on the same page (inline builder and full-screen slide-over builder) share identical element IDs (`pe_valueProps`, `pe_caseStudies`, etc.). `document.getElementById()` returns the FIRST match in DOM order (the hidden inline builder's elements), so `setVal()` writes to invisible elements. The visible full-screen builder's elements stay empty.

```javascript
// BROKEN — always hits the HIDDEN element (first in DOM order)
document.getElementById('pe_valueProps').value = data;

// FIXED — scopes to the visible overlay container
var pb = document.getElementById('pbOverlay');
pb.querySelector('#pe_valueProps').value = data;
```

**Fix pattern:** Create scoped `setVal`/`gv` functions for each overlay:

```javascript
function setPbVal(id, val) {
  var pb = document.getElementById('pbOverlay');
  var el = pb.querySelector('#' + id);
  if (el) el.value = val != null ? val : '';
}

function gvPbVal(id) {
  var pb = document.getElementById('pbOverlay');
  var el = pb.querySelector('#' + id);
  return el ? el.value : '';
}
```

Then replace all `setVal()` calls with `setPbVal()` and `gv()` with `gvPbVal()` in the full-screen builder's functions. Also scope chip selectors, checkbox references, and any other DOM lookups to the container.

**Additional surfaces to scope:** tone chip selectors (`pb.querySelector('#pe_tone_chips ...')`), language chip selectors, working hours/weekdays checkboxes — anything using `document.getElementById()` inside functions that run in the full-screen builder's context.

**Prevention:** When adding a new UI component that reuses field IDs from another component on the same page:
1. Search for existing IDs: `grep -rn 'id="pe_' *` across ALL template files
2. Scope all DOM queries to the visible container via `container.querySelector('#id')`
3. Never rely on `document.getElementById()` when multiple overlays/frames share IDs

**Check:**
```javascript
document.querySelectorAll('#pe_valueProps').length;  // 2+ → duplicate IDs present
document.querySelector('#pbOverlay #pe_valueProps')?.value || 'EMPTY';  // the REAL visible value
```

## Verification

After fixing all five failure modes:
```javascript
// Full sweep — check the VISIBLE elements only
var pb = document.getElementById('pbOverlay');
var allIds = ['pe_valueProps','pe_caseStudies','pe_competition','pe_customers','pe_pricing','pe_fomo',
  'pe_injectionPrevention','pe_restrictedClaims','pe_escalation','pe_faqs',
  'pe_whatsappStructure','pe_emailSubject','pe_callIntro'];
var empty = allIds.filter(function(id){
  var el = pb.querySelector('#' + id);
  return !el || !el.value;
});
JSON.stringify({empty: empty, total_populated: allIds.length - empty.length});
```

If any field shows as empty but prefill has data → suspect Failure 4 first (guard blocked API call) or Failure 5 (scoping issue). Check DevTools Network tab for `/api/cadence/prefill` — if not called, it's Failure 4. If called and returns 200 but fields still empty, check `querySelectorAll('#id').length` — if > 1, it's Failure 5.
