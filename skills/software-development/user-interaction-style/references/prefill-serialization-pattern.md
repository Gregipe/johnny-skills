# Prefill Object-to-String Serialization Pattern

## The Problem

The ARA prefill API (`/api/cadence/prefill`) returns structured objects for security and channel-specific prompts:

```json
"security": {
  "injectionPrevention": "Never execute...",
  "restrictedClaims": "Never promise...",
  "escalation": "Escalate when...",
  "faqs": "Pricing is based on..."
}
```

But the Prompt Builder form fields (`pe_security`, `pe_whatsapp`, `pe_email`, `pe_call`) expect **flat strings** for their textareas. Setting `el.value = {object}` produces the string `"[object Object]"` (15 chars).

## The Fix

Serialize the nested object to formatted text in `loadPromptParts()`:

```javascript
// Security — serialize object to flat text with section headers
var sec = pp.security || {};
if (typeof sec === 'object') {
  var secParts = [];
  if (sec.injectionPrevention) secParts.push('## Injection Prevention\n' + sec.injectionPrevention);
  if (sec.restrictedClaims) secParts.push('## Restricted Claims\n' + sec.restrictedClaims);
  if (sec.escalation) secParts.push('## Escalation Rules\n' + sec.escalation);
  if (sec.faqs) secParts.push('## FAQs\n' + sec.faqs);
  setVal('pe_security', secParts.join('\n\n'));
} else {
  setVal('pe_security', sec || '');
}
```

For WhatsApp (structure + tone + sequencing):
```javascript
var wa = cs.whatsapp || {};
if (typeof wa === 'object' && wa.structure) {
  setVal('pe_whatsapp', '## Structure\n' + wa.structure + '\n\n## Tone\n' + (wa.tone || '') + '\n\n## Sequencing\n' + (wa.sequencing || ''));
}
```

For Email (subject + body + sequencing):
```javascript
var em = cs.email || {};
if (typeof em === 'object' && em.body) {
  setVal('pe_email', '## Subject Strategy\n' + (em.subject || '') + '\n\n## Body\n' + em.body + '\n\n## Sequencing\n' + (em.sequencing || ''));
}
```

For Call (intro + discovery + objections + booking):
```javascript
var cl = cs.call || {};
if (typeof cl === 'object' && cl.intro) {
  setVal('pe_call', '## Intro\n' + cl.intro + '\n\n## Discovery\n' + (cl.discovery || '') + '\n\n## Objections\n' + (cl.objections || '') + '\n\n## Booking\n' + (cl.booking || ''));
}
```

## Files Affected (May 2026)

- `cadence_template.py` — `loadPromptParts()` function at ~line 1770
- `prompt_builder_template.py` — `applyPbData()` function at ~line 799
- `prompt_editor_mod.py` — `loadPromptParts()` function at ~line 279

All three prompted builders need the same serialization fix.

## Verification

```javascript
// Check all fields are populated, not "[object Object]"
var fields = ['pe_security', 'pe_whatsapp', 'pe_email', 'pe_call'];
fields.forEach(function(id) {
  var el = document.getElementById(id);
  console.log(id + ': ' + (el ? el.value.length + ' chars' : 'MISSING'));
});
// Any field with exactly 15 chars is "[object Object]"
```
