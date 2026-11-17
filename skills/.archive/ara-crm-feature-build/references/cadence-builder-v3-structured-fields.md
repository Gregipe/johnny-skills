# Cadence Builder v3 — Structured Fields & Brand Voice System

## Overview

The Cadence Builder at `/cadence` uses structured step fields (per-channel) + a Brand Voice system (tone, no-nos, formality) + LLM-generated preview on demand. This file documents the implementation details and critical pitfalls discovered during v3 development.

## Per-Channel Structured Fields

Each channel type gets its own set of objective fields. The user writes exactly what goes where; the LLM fills in good language around the structure.

```javascript
var STEP_FIELDS = {
  whatsapp: [
    {key:'opening', label:'Opening', placeholder:'Hook / personalization'},
    {key:'value', label:'Value', placeholder:'Core value proposition'},
    {key:'cta', label:'CTA', placeholder:'Call to action'}
  ],
  email: [
    {key:'subject', label:'Subject', placeholder:'Email subject line'},
    {key:'opening', label:'Opening', placeholder:'First paragraph'},
    {key:'body', label:'Body', placeholder:'Value prop / details'},
    {key:'cta', label:'CTA', placeholder:'Call to action'}
  ],
  call: [
    {key:'greeting', label:'Greeting', placeholder:'Context / opener'},
    {key:'value', label:'Value', placeholder:'Why call now'},
    {key:'question', label:'Question', placeholder:'Key discovery question'},
    {key:'cta', label:'CTA', placeholder:'Closing ask'}
  ],
  sms: [
    {key:'hook', label:'Hook', placeholder:'One-line value'},
    {key:'cta', label:'CTA', placeholder:'Next step'}
  ]
};

function defaultFields(channel) {
  var fields = {};
  (STEP_FIELDS[channel] || []).forEach(function(f) { fields[f.key] = ''; });
  return fields;
}
```

### Step Data Structure

```javascript
// In localStorage (ara_cadence_data):
{channel:'whatsapp', day:0, delay:0, fields:{opening:'...', value:'...', cta:'...'}}

// Default (Cold Outreach):
[
  {channel:'whatsapp', day:0, delay:0, fields:{opening:'Reference their recent expansion/growth', value:'Voice AI handles initial screening autonomously', cta:'Worth 2 min to see if it fits?'}},
  {channel:'email', day:1, delay:24, fields:{subject:'Quick thought on scaling hiring at {{company}}', opening:'Noticed {{company}} expanding — impressive growth', body:'Hunar\'s voice AI handles first-round screening autonomously', cta:'Worth a quick 10-min chat?'}},
  {channel:'call', day:3, delay:48, fields:{greeting:'Hi {{name}}, this is Greg from Hunar — following up on my email', value:'I know {{company}} is growing', question:'How are you handling initial candidate screening today?', cta:'Would a 15-min demo this week make sense?'}},
  {channel:'whatsapp', day:5, delay:48, fields:{opening:'Quick follow-up — did you get a chance to check the demo?', value:'Teams like {{company}} cut screening time by 70%', cta:'Happy to jump on a quick call this week?'}}
]
```

### Migration from Old `desc` Format

In `loadData()`, detect old steps that lack `fields` and convert them:

```javascript
(data[key].steps || []).forEach(function(s) {
  if (!s.fields) {
    s.fields = defaultFields(s.channel);
    if (s.desc) {
      var firstKey = Object.keys(s.fields)[0];
      if (firstKey) s.fields[firstKey] = s.desc;
    }
  }
});
```

This runs on every `loadData()` call — handles both fresh installs and corrupted localStorage.

### Rendering Structured Fields

In `renderSteps()`, iterate `STEP_FIELDS[s.channel]` and render each as an `.sf-row`:

```javascript
var fieldsDef = STEP_FIELDS[s.channel] || STEP_FIELDS.whatsapp;
var stepFields = s.fields || defaultFields(s.channel);
fieldsDef.forEach(function(f) {
  var val = stepFields[f.key] || '';
  fieldsHtml += '<div class="sf-row"><span class="sf-label">' + f.label + '</span>' +
    '<input class="sf-input" data-step="' + i + '" data-field="' + f.key + '" value="' +
    val.replace(/"/g,'&quot;') + '" placeholder="' + f.placeholder + '"></div>';
});
```

### Saving Structured Fields

In `saveCurrentState()`, read fields from the DOM by querying `sf-input` elements:

```javascript
var stepCards = document.querySelectorAll('#stepsContainer .step-card');
stepCards.forEach(function(card, i) {
  if (i < (t.steps || []).length) {
    var fields = t.steps[i].fields || {};
    card.querySelectorAll('.sf-input').forEach(function(inp) {
      var stepIdx = parseInt(inp.getAttribute('data-step'));
      if (stepIdx === i) {
        fields[inp.getAttribute('data-field')] = inp.value;
      }
    });
    t.steps[i].fields = fields;
  }
});
```

**CRITICAL: NEVER clear `t.steps` before re-saving.** The bug was `t.steps = []` followed by a broken forEach loop. The steps array must be preserved (channel, day, delay) while the DOM provides field descriptions.

### CSS (compact, per-step)

```css
.sf-row { display:flex; align-items:center; gap:4px; margin-bottom:3px; }
.sf-label { font-size:9px; font-weight:600; color:#8A8A8E; width:44px; flex-shrink:0; text-align:right; }
.sf-input { flex:1; padding:5px 8px; border:1px solid #E8E8ED; border-radius:5px; font-size:10px; background:#FAFAFC; }
.sf-input:focus { border-color:#111; background:#fff; }
```

## Brand Voice System

Three controls per template (saved per-template in localStorage):

1. **Tone chips** — Formal / Warm & direct / Casual / Funny (single-select, via `data-tone`)
2. **No-nos tags** — editable list of forbidden phrases, addable via inline button, removable via ✕
3. **Formality slider** — 1-5 range, with labels: Casual → Mostly casual → Warm & direct → Polished → Formal

### CRITICAL PITFALL: Brand Voice Memory Sync

When a visual UI control (tone chip click, formality slider change) updates brand voice state, the handler MUST write the new value to `getTemplate().brandVoice` in memory. The visual DOM is NOT the source of truth. If you update a CSS class or label text without syncing to the in-memory model, any downstream function that reads `t.brandVoice` (preview generation, save, API call) will get stale data.

**WRONG** (only updates visual):
```javascript
chip.classList.add('active');  // visual only — memory still has old tone
markUnsaved();
if (selectedStepIndex >= 0) generatePreview(selectedStepIndex);  // sends OLD tone to API
```

**RIGHT** (syncs to memory first):
```javascript
chip.classList.add('active');
var t = getTemplate();
if (t) t.brandVoice.tone = chip.dataset.tone;  // sync to memory
markUnsaved();
```

Same applies to formality slider changes:
```javascript
var val = parseInt(e.target.value);
document.getElementById('formalityLabel').textContent = FORMALITY_LABELS[val - 1];
var t = getTemplate();
if (t) t.brandVoice.formality = val;  // sync to memory
```

This applies to ANY visual-only state change that feeds into a downstream operation — not just brand voice. Always ask: "Is the in-memory model in sync with the visual DOM before I do something that reads the model?"

## Manual Preview Generation (User Preference)

The user explicitly requested that preview does NOT auto-regenerate on any click, change, or selection. Preview ONLY generates when the 🤖 ⟳ Regenerate button is clicked.

### Implementation

- `selectStep()` → calls `resetPreview()` (shows "Click Regenerate to preview" empty state)
- Tone/formality/field changes → only saves to memory, no preview call
- Regenerate button → reads current memory state (step data, brand voice, objective) → calls `POST /api/cadence/preview` → renders response
- Initial page load → selects first step, shows step info in header, preview shows empty state

```javascript
function resetPreview() {
  document.getElementById('previewBody').className = 'preview-empty';
  document.getElementById('previewBody').innerHTML = '🤖 Click <strong>⟳ Regenerate</strong> to preview<br>Ava\'s generated communication';
  document.getElementById('previewStep').textContent = '';
}
```

The preview header always shows which step is selected (channel + step number), but the body stays empty until regenerate is clicked.

## Event Delegation + Input Click Trap

The step cards have `data-action="select-step"` on the outer div. The delegated event listener uses `e.target.closest('[data-action]')`, which finds the step card even when clicking an input field inside it.

**The fix:** Check `e.target.tagName` before triggering step selection:

```javascript
} else if (action === 'select-step') {
  var clickedEl = e.target;
  if (clickedEl.tagName === 'INPUT' || clickedEl.tagName === 'TEXTAREA' || clickedEl.tagName === 'BUTTON') return;
  selectStep(parseInt(t.dataset.stepIndex));
}
```

Without this check, clicking any structured field input triggers `selectStep()`, which calls `saveCurrentState()` + `renderSteps()` + `resetPreview()` — re-rendering the DOM and stealing focus from the input the user was trying to edit.

## Delay Editor — Hour Normalization (0–23, Overflow → Days)

### Problem

The delay editor previously allowed any value in the hours field (max="999"). Users could type 48h, 72h, or even 500h — which should logically be expressed as days + remaining hours.

### Solution

**Constraint:** Hours input is capped to `0–23` via HTML `max="23"` attribute.

**Display:** The initial value shows `s.delay % 24` (the remainder), so existing data with 48 delay shows as 0h with the day incremented correctly.

```javascript
span.innerHTML = '...' +
  '<input type="number" min="0" max="23" value="' + (s.delay % 24) + '" ...class="delay-hr-input"> ' +
  'h ...';
```

**Normalization on save:** In `doneDelay()`, roll overflow hours into days:

```javascript
var days = parseInt(dayInput.value) || 0;
var hours = parseInt(hrInput.value) || 0;
// Normalize: hours 0-23, overflow rolls to days
days += Math.floor(hours / 24);
hours = hours % 24;
t.steps[index].day = days;
t.steps[index].delay = hours;
```

### Behavior

| User types | Result |
|-----------|--------|
| hours = 0 → 23 | Stored as-is |
| hours = 25 | Day +1, 1h |
| hours = 48 | Day +2, 0h |
| hours = 72 | Day +3, 0h |

The delay text display uses `(s.day > 0 ? 'Day ' + s.day : '') + (s.delay > 0 ? ' · +' + s.delay + 'h' : '') || 'Day 0 · +0h'`.

## Drag-and-Drop Reorder (HTML5 Native)

### Implementation

Each step card is marked `draggable="true"` with `data-drag="step"`. A `⠿` drag handle appears on the left of each card.

### Event Handlers

```javascript
var dragSrcIdx = -1;

document.addEventListener('dragstart', function(e) {
  var card = e.target.closest('[data-drag="step"]');
  if (!card) return;
  dragSrcIdx = parseInt(card.dataset.stepIndex);
  card.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', dragSrcIdx);
});

document.addEventListener('dragend', function(e) {
  // Clean up all drag classes
});

document.addEventListener('dragover', function(e) {
  var card = e.target.closest('[data-drag="step"]');
  if (!card || dragSrcIdx < 0) return;
  e.preventDefault();
  card.classList.add('drag-over');
});

document.addEventListener('drop', function(e) {
  var card = e.target.closest('[data-drag="step"]');
  if (!card || dragSrcIdx < 0) return;
  e.preventDefault();
  var targetIdx = parseInt(card.dataset.stepIndex);
  if (dragSrcIdx === targetIdx) return;
  var t = getTemplate();
  var step = t.steps.splice(dragSrcIdx, 1)[0];
  t.steps.splice(targetIdx, 0, step);
  saveData();
  selectedStepIndex = targetIdx;
  renderSteps();
  resetPreview();
  markUnsaved();
});
```

### CSS for Drag States

```css
.drag-handle { font-size:13px; color:#C0C0C5; cursor:grab; user-select:none; }
.drag-handle:active { cursor:grabbing; }
.step-card.dragging { opacity:0.4; border-color:#111; border-style:dashed; }
.step-card.drag-over { border-color:#2563eb; border-style:dashed; background:#F8FAFF; }
```

The `data-step-index` attribute on each card is reassigned by `renderSteps()` after the splice, so the next drag operation reads correct indices.

## LLM Preview Endpoint

`POST /api/cadence/preview` on the Python backend:

### Request Body
```json
{
  "step": {"channel": "whatsapp", "fields": {"opening": "...", "value": "...", "cta": "..."}},
  "brandVoice": {"tone": "warm", "nonos": ["...", "..."], "formality": 3},
  "templateName": "Outbound (Cold Outreach)",
  "leadName": "Rajesh",
  "leadCompany": "Acme Manufacturing",
  "leadCity": "Pune",
  "leadIndustry": "manufacturing"
}
```

### System Prompt Construction

The endpoint builds a system prompt with:
1. Channel-specific format guidelines
2. Tone + formality description
3. "NEVER use" constraints from no-nos
4. Field-by-field instructions — each non-empty field becomes a line like `  Subject line: Quick thought on scaling...`
5. Lead context (name, company, city, industry)
6. Step objective (from `step.desc`, kept for backward compatibility)

```python
parts = []
for k, v in fields.items():
    if v:
        label = field_mapping.get(k, k + ": ")
        parts.append(f"  {label}{v}")
if parts:
    field_text = "Field-by-field content to include:\n" + "\n".join(parts) + "\n"
```

The prompt instructs the LLM to respond with ONLY the message text — no explanations, quotes, or markdown.

### Field-to-Label Mapping

```python
field_mapping = {
    "subject": "Subject line: ",
    "opening": "Opening/hook: ",
    "body": "Body/content: ",
    "value": "Value proposition: ",
    "greeting": "Greeting: ",
    "question": "Key question: ",
    "cta": "Call to action: ",
    "hook": "Hook/message: "
}
```

### Fallback

If the LLM call fails, falls back to `staticFallback(channel)` which returns hardcoded sample text per channel.

## Per-Template State Management

Each template (Cold/Inbound/Nurture) has its own:
- Brand Voice (tone, nonos, formality)
- Primary goal (objective text)
- Steps (channel, delay, fields)
- Conditions (reachout + stop)

All persisted to a single `localStorage` key (`ara_cadence_data`). On template switch, unsaved changes prompt before loading the other template's state.

### localStorage Corruption Recovery

If a prior bug saved empty step arrays, `loadData()` must detect and repair:

```javascript
if (!data[key].steps || data[key].steps.length === 0) {
  data[key].steps = JSON.parse(JSON.stringify(DEFAULT_TEMPLATES[key].steps));
}
```

Always validate saved data before trusting it. A secondary bug (the `t.steps = []` in `saveCurrentState()`) corrupted user data — the recovery code handles it.
