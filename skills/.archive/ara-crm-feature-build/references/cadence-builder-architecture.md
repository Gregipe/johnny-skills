# Cadence Builder Architecture (May 2026 v2)

## Overview
Configuration page for designing outreach cadences (Cold Outreach, Inbound, Nurture/ABM). Standalone page served from `/cadence` route. No Ava chat panel (config screen).

## File Structure
- `cadence_template.py` — Full HTML/CSS/JS template (exported as `CADENCE_HTML` via raw string `r"""..."""`).
- `server.py` — Imports `CADENCE_HTML`, serves at `@app.get("/cadence")`.
- `dashboard_template.py` — Adds "Outbound Cadence" nav item pointing to `/cadence`.

## Layout (v2 — Refined May 23, 2026)
```
[sidenav 240px (same as dashboard, "Outbound Cadence" active)] [content-wrap flex:1, scrollable]

  [Mapping Strip — static row, across all templates, unchanged]

  [❄️ Cold Outreach] [🔥 Inbound (Hot Lead)] [🌱 Nurture / ABM]  — 3 template cards

  🎨 Brand Voice — [active template name]
    Tone: [Formal] [Warm & direct] [Casual] [Funny]  |  🚫 No-nos: ["Buzzwords"✕] [+ Add]
    Formality: Casual ───○─── Warm & direct  1  2  3  4  5

  50-50 split:
  ┌──────────────────────────────────┬──────────────────────────────────┐
  │ LEFT COLUMN                      │ RIGHT COLUMN                    │
  │                                  │                                 │
  │ 🎯 Primary Goal                  │ ┌─ Preview ──────────────────┐ │
  │ [______________________________] │ │ 💬 Step 1  [⟳ Regenerate]  │ │
  │                                  │ │ → {{first_name}}, Mfg       │ │
  │ ┌─ 💬 WhatsApp ───────────────┐  │ │                              │ │
  │ │ Day 0 · +0h ✏️            │  │ │ Hey {{first_name}} 👋...    │ │
  │ │ [Warm intro + value hook]  │  │ │                              │ │
  │ └─────────────────────────────┘  │ └──────────────────────────────┘ │
  │ ┌─ ✉️ Email ─────────────────┐  │                                  │
  │ │ Day 1 · +24h ✏️           │  │ ┌─ 🟢 Reachout ─┬─ 🔴 Stop ──┐  │
  │ │ [Detailed value prop...]   │  │ │ ☑ Working hrs │ ☑ Replied  │  │
  │ └─────────────────────────────┘  │ │ ☑ Weekdays    │ ☑ Opt out  │  │
  │ [+ Add Step]                    │ └────────────────┴─────────────┘  │
  └──────────────────────────────────┴──────────────────────────────────┘
```

Key changes from v1 (pre-rewrite):
- **Brand directives added** between template cards and the 50-50 split. Per-template: tone chips (4 options), no-nos tags (editable, deletable, +Add), formality slider (1-5).
- **Outreach Goals (numbered rules 1,2,3) removed** — replaced by a single **Primary Goal** text input.
- **Steps as clickable cards** each showing channel icon + name + inline-editable delay + objective textbox. No drag-to-reorder.
- **Preview panel** — the right column's primary content. Shows sample message with `{{variables}}` highlighted. Content varies by channel:
  - WhatsApp: full message text with emoji support
  - Email: To/Subject lines + body + Calendly link + signature
  - Call: talking-points outline (numbered flow: greeting, value statement, key question, CTA)
  - SMS: short, punchier than WhatsApp
- **Conditions moved** below the preview in right column, side-by-side as two equal tiles. Not at page bottom.
- **Temperature per step removed** — formality is brand-level only.
- **Step picker modal** — clicking "+ Add Step" opens a modal with 4 channel buttons (WhatsApp, Email, Call, SMS).
- **Template switching** with unsaved-changes confirmation modal.

## Templates (Per-Template State)

Three fixed templates (Cold, Inbound, Nurture). Each has its OWN full state:

```javascript
{
  id: 'cold',
  title: 'Outbound (Cold Outreach)',
  desc: 'First-touch prospecting for net-new leads',
  icon: '🎯',
  iconClass: 'cold',
  objective: 'Book introductory discovery call with qualified leads',
  brandVoice: {
    tone: 'warm',          // formal | warm | casual | funny
    nonos: ['"I wanted to reach out"', 'Buzzwords', 'Emojis in email'],
    formality: 3           // 1-5
  },
  conditions: {
    workingHours: true,
    weekdays: true,
    saturday: false,
    sunday: false
  },
  stopConditions: {
    meetingBooked: true,
    optOut: true,
    notInterested: false
  },
  steps: [
    {channel: 'whatsapp', day: 0, delay: 0, desc: 'Warm intro + value hook'},
    {channel: 'email', day: 1, delay: 24, desc: 'Detailed value prop with case study'},
    {channel: 'call', day: 3, delay: 48, desc: 'Follow-up call — address objections'},
    {channel: 'whatsapp', day: 5, delay: 48, desc: 'Gentle re-engage'}
  ]
}
```

### Template Presets (Default Step Sequences)

| Template | Steps |
|----------|-------|
| **Cold Outreach** | 💬 WhatsApp (Day 0, +0h) → ✉️ Email (Day 1, +24h) → 📞 Call (Day 3, +48h) → 💬 WhatsApp (Day 5, +48h) |
| **Inbound (Hot Lead)** | ✉️ Email (Day 0, +0h) → 📞 Call (Day 1, +24h) → 💬 WhatsApp (Day 3, +48h) |
| **Nurture / ABM** | ✉️ Email (Day 0, +0h) → ✉️ Email (Day 3, +72h) → 📞 Call (Day 7, +96h) |

## Persistence

- **localStorage** keyed as `ara_cadence_data` — saves all 3 templates' full state.
- "Publish Cadence" calls `saveCurrentState()` then `saveData()` — saves current template to localStorage.
- "Reset to Default" restores selected template from `DEFAULT_TEMPLATES` (with confirmation modal).
- Template switching: `selectTemplate(id)` checks for unsaved changes first. If detected, shows a modal: "You have unsaved changes. Switch anyway?"
- The `saveCurrentState()` function reads: goal input, brand voice DOM (active tone chip, nono chips' text, formality slider value), step objectives from DOM input values, and conditions/stopConditions checkboxes.

### Pitfall: Never Clear `t.steps` in saveCurrentState

A bug was introduced and fixed where:

```javascript
// WRONG — clears steps before reading back, destroying channel/day/delay
t.steps = [];
stepCards.forEach(function(card) {
  var idx = parseInt(card.dataset.stepIndex);
  // ...does nothing with idx...
});
var existing = t.steps || [];  // empty! data wiped.
```

The fix: **never set `t.steps = []` in saveCurrentState**. The step array carries `channel`, `day`, `delay` that the DOM cards don't expose. Only update `.desc` from the DOM inputs in-place:

```javascript
// RIGHT — update descriptions only, preserve channel/timing from memory
stepCards.forEach(function(card, i) {
  if (i < (t.steps || []).length) {
    var obj = card.querySelector('.step-objective');
    if (obj) t.steps[i].desc = obj.value;
  }
});
```

**Rule:** When saving state from DOM to a data structure, only update the fields the DOM represents. Never reinitialize the parent array unless you're re-reading EVERY field from the DOM.

## Brand Voice Bar (NEW)

Between template cards and the 50-50 split. Lives inside `.brand-bar`:

| Control | DOM elements | JS handler |
|---------|-------------|------------|
| Tone | `.tone-chip` with `data-tone` (formal/warm/casual/funny) | Click via event delegation, toggle `.active` class |
| No-nos | `.nono-chip` with `data-nono` attribute + `.nono-add` button | Click `.x` to delete, click `#addNonoBtn` → `addNono()` via `prompt()` |
| Formality | `#formalitySlider` (range 1-5) + `#formalityLabel` | `input` event updates label from `FORMALITY_LABELS` array |

## Step Cards (Left Column)

Clickable cards with `data-action="select-step"` and `data-step-index`. Clicking a step:
1. Highlights the card (`.active` class)
2. Calls `generatePreview(index)` — renders the preview on the right

Each card shows:
- Channel icon (SVG wrap: WhatsApp green, Email blue, Call indigo, SMS gray)
- Channel name (`WhatsApp`, `Email`, `Call`, `SMS`)
- Delay text (e.g., `Day 0 · +0h ✏️`). Clicking the delay span triggers `editDelay(index)` which replaces the span with Day + Hours number inputs + a ✓ done button. `doneDelay(index)` reads the inputs, saves to template.steps, and re-renders.
- Objective text input — edits are auto-saved to `t.steps[index].desc` on every `input` event via event delegation on `step-objective` class.
- Delete button (✕) — calls `deleteStep(index)`. Blocks deletion if only 1 step remains.

## Preview Content by Channel

Preview is generated by `generatePreview(index)`. Uses template data + sample lead context (hardcoded as "Rajesh Sharma, Acme Manufacturing, Pune, manufacturing"). Content varies by channel:

**WhatsApp preview:** Full conversational message with emojis, `{{first_name}}`, `{{company}}`, `{{city}}` variables. Warm tone, Calendly CTAs. No subject line. Variables highlighted via `<span class="var">`.

**Email preview:** Shows To/Subject lines before the body in monospace:
```
To: Rajesh@example.com
Subject: Quick thought on scaling hiring at {{company}}

Hi {{first_name}},
...body with {{company}}, {{city}} references...
[Calendly link]

— Greg
Hunar.ai
```
Subject line is generated from context, not user-editable in current UI.

**Call preview:** Numbered talking-points outline:
```
📞 Call Script — {{first_name}}, {{company}}

🎯 Objective: [step description]

1️⃣ Greeting & context
   "Hi {{first_name}}, this is Greg from Hunar..."
2️⃣ Value statement
   "I know {{company}} is expanding in {{city}}..."
3️⃣ Key question
   "How are you currently handling initial candidate screening?"
4️⃣ CTA
   "Would a 15-min demo this week make sense?"
```

**SMS preview:** Short single punchy paragraph. No subject line, shorter CTA with `{{link}}` variable. Punched up tone — emoji optional.

Regenerate button (⟳) re-runs `generatePreview(index)` with the same data (refreshes the preview).

## Step Picker Modal

When "+ Add Step" is clicked, a centered modal overlay opens with 4 channel buttons:
- WhatsApp (green icon)
- Email (blue icon)
- Call (indigo icon)
- SMS (gray icon)

Clicking a button calls `addStep(channel)`:
1. Closes the modal
2. Appends `{channel, day:0, delay:0, desc:''}` to `t.steps`
3. Re-renders steps
4. Selects the new step and generates its preview

## Conditions (Right Column, Below Preview)

Two cards side-by-side in `.cond-inline`:

**Reachout Conditions:** Working hours (9AM-6PM), Weekdays only, Saturday, Sunday.

**Stop Conditions:** Lead replied/engaged, Opted out/unsubscribed, Not interested.

All are checkboxes with per-template saved state. Changes are persisted via `saveCurrentState()`.

## JS Architecture

- `loadData()` / `saveData()` — localStorage read/write with deep-cloned defaults fallback. Migration: if `brandVoice` missing from saved data, fills from defaults.
- `renderTemplates()` — renders 3 template selector cards with event delegation.
- `renderBrandVoice()` — populates tone chips, no-nos tags, formality slider from `t.brandVoice`.
- `renderSteps()` — renders step cards from `t.steps`. `selectedStepIndex` controls which card has `.active` class.
- `renderCurrentTemplate()` — full page render from template state. Calls `renderBrandVoice()`, `renderSteps()`, loads conditions and goal.
- `selectTemplate(id)` — checks for unsaved changes, shows confirmation modal if needed, then saves current and loads new.
- `selectStep(index)` — saves current state, sets `selectedStepIndex`, re-renders steps, generates preview.
- `generatePreview(index)` — renders channel-specific preview with `{{variables}}` highlighted.
- `saveCurrentState()` — reads all DOM fields into the current template object. **MUST NOT** clear `t.steps` (see pitfall above).
- `checkUnsaved()` — compares goal input against saved value; tracks `hasUnsavedChanges` flag.
- `addStep(channel)` / `deleteStep(index)` / `editDelay(index)` / `doneDelay(index)` — step management.
- `addNono()` — prompts for text, adds to `t.brandVoice.nonos`, re-renders brand bar.

## Formality Labels

```javascript
var FORMALITY_LABELS = ['Casual', 'Mostly casual', 'Warm & direct', 'Polished', 'Formal'];
```

Slider value 1-5 maps to these labels. Displayed live on input event.

## CSS Layout Classes

```css
.body-split { display: flex; gap: 36px; }
.left-col { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 10px; }
.right-col { width: 460px; flex-shrink: 0; display: flex; flex-direction: column; gap: 10px; }
.brand-bar { background: #F8F8FA; border: 1px solid #E5E5E7; border-radius: 12px; padding: 16px 20px; margin-bottom: 20px; }
.brand-row { display: flex; gap: 28px; align-items: center; flex-wrap: wrap; }
.cond-inline { display: flex; gap: 12px; }
.cond-card { flex: 1; background: #fff; border: 1px solid #E5E5E7; border-radius: 12px; padding: 14px 16px; }
.preview-card { flex: 1; border: 1px solid #E5E5E7; border-radius: 12px; overflow: hidden; min-height: 280px; }
.picker-overlay { position: fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,.3); z-index:200; }
.picker-modal { background: #fff; border-radius: 14px; padding: 24px; width: 380px; }
.confirm-overlay { position: fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,.3); z-index:300; }
.goal-card { padding: 16px 18px; border: 1px solid #E5E5E7; border-radius: 12px; }
.step-card { padding: 14px 16px; border: 1px solid #E5E5E7; border-radius: 12px; cursor: pointer; }
.step-card.active { border-color: #111; box-shadow: 0 0 0 1px rgba(0,0,0,.15); }
.tone-chip { padding: 4px 10px; border-radius: 100px; border: 1px solid #E5E5E7; font-size: 10px; cursor: pointer; }
.tone-chip.active { background: #111; border-color: #111; color: #fff; }
.nono-chip { font-size: 10px; padding: 3px 8px; border-radius: 100px; background: #FFF0F0; color: #C62828; border: 1px solid #FFCDD2; cursor: pointer; }
```

## Lead-to-Cadence Mapping (Top-Level Static Row)

Displayed as a compact horizontal strip (`mapping-strip`) at the very top of the page (below header, above template cards):
- Reachout + Inbound → Inbound
- Reachout + Outbound → Cold Outreach
- Dormant / Churned → Nurture/ABM
- Booked / Won → Out of scope

This is prescriptive and not user-editable. Stays in the same position regardless of which template is selected.

## Debugging

If the cadence page shows old layout (pre-rewrite): kill all Python processes on port 8766, restart server. The old file may have been cached by a leftover process.

If template cards or steps don't show on reload: open browser console and check `localStorage.getItem('ara_cadence_data')`. If corrupted, run `localStorage.removeItem('ara_cadence_data')` and reload — this triggers fresh defaults from `DEFAULT_TEMPLATES`.
