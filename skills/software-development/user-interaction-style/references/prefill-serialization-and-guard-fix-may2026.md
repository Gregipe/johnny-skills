# Prefill Serialization & Guard Fix — May 29, 2026

## The Problem

Three separate issues prevented the Prompt Builder tabs from being pre-filled with induction data:

### Issue 1: Object-to-String Serialization Gap

The prefill API returns structured objects:
```javascript
{
  security: { injectionPrevention: "...", restrictedClaims: "...", escalation: "...", faqs: "..." },
  channelSpecific: {
    whatsapp: { structure: "...", tone: "...", sequencing: "..." },
    email: { subject: "...", body: "...", sequencing: "..." },
    call: { intro: "...", discovery: "...", objections: "...", booking: "..." }
  }
}
```

But `loadPromptParts()` did:
```javascript
setVal('pe_security', pp.security || '');     // → "[object Object]" (15 chars)
setVal('pe_whatsapp', cs.whatsapp || '');     // → "[object Object]" (15 chars)
```

JavaScript's `el.value = {object}` produces `"[object Object]"` — a 15-char string that looks populated but is meaningless.

**Fix:** Serialize objects into flat formatted text:
```javascript
var sec = pp.security || {};
if (typeof sec === 'object') {
  var parts = [];
  if (sec.injectionPrevention) parts.push('## Injection Prevention\n' + sec.injectionPrevention);
  if (sec.restrictedClaims) parts.push('## Restricted Claims\n' + sec.restrictedClaims);
  if (sec.escalation) parts.push('## Escalation Rules\n' + sec.escalation);
  if (sec.faqs) parts.push('## FAQs\n' + sec.faqs);
  setVal('pe_security', parts.join('\n\n'));
}
```

Same pattern for WhatsApp, Email, Call channel prompts — concatenate structure, tone, sequencing into flat text.

### Issue 2: Prefill Guard Blocks API Call

The inline builder's `prefillFromInduction()` at `cadence_template.py:~2050` had:
```javascript
if (globalPromptParts && globalPromptParts.brandPersonality) return; // Already has global data
```

The full-screen builder's `loadPromptBuilderData()` at `prompt_builder_template.py:~798` had:
```javascript
if (!pp.brandPersonality && !cache.brandPersonality) { fetch(...) }
```

Both used `brandPersonality` as a proxy for "all data is present." The `migrateToGlobalPromptParts()` function runs on EVERY page load and creates `globalPromptParts` from old template data — which may have `brandPersonality` (with tone, style, vocabulary) but EMPTY `sectorSpecific`. Result: guard returns early, prefill API is never called, sector fields stay blank.

**Fix:** Check for the SPECIFIC missing field:
```javascript
if (globalPromptParts && globalPromptParts.sectorSpecific && globalPromptParts.sectorSpecific.valueProps) return;
```

**Two separate guard conditions to fix:**
- `cadence_template.py` line ~2052 (inline builder)
- `prompt_builder_template.py` line ~798 (full-screen builder)

### Issue 3: Missing Textareas in Collapsed Cards

The full-screen builder (`prompt_builder_template.py`) uses collapsible cards for sector fields. Only "Value Proposition" was expanded by default with a textarea; the other 6 cards (Case Studies, Competitor References, Existing Customers, Pricing References, FOMO Triggers, Deck/Data References) had collapsible headers with `+` toggle buttons but NO textarea body elements.

**Fix:** 
- Added `expanded` class and `−` toggle to all 6 cards
- Added `<div class="pb-mod-card-body">` with `<textarea>` elements and unique IDs (`pe_caseStudies`, `pe_competition`, etc.)
- Updated `applyPbData()` to fill all 7 sector fields (was only filling `pe_valueProps`)
- Updated `collectPbData()` to save all 7 sector fields (was only saving `valueProps`)

## How to Verify

After ALL fixes, on a fresh page load:

```javascript
// Inline builder
openPromptEditor();
switchTab('sector');
var fields = ['pe_valueProps','pe_caseStudies','pe_competition','pe_customers','pe_pricing','pe_fomo','pe_deckRef'];
fields.forEach(function(id) {
  console.log(id + ': ' + (document.getElementById(id)?.value?.length + ' chars' || 'NOT FOUND'));
});
```

Expected: all field lengths > 0 except `pe_deckRef`.

## Files Modified

| Fix | Files |
|-----|-------|
| Object serialization | `cadence_template.py` (loadPromptParts) |
| Prefill guard | `cadence_template.py`, `prompt_builder_template.py` |
| Missing textareas | `prompt_builder_template.py` (sector card HTML + applyPbData + collectPbData) |
| Missing tone option | `cadence_template.py` (added "persuasive" to pe_tone select) |
