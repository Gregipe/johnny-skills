# Cadence Builder v2 — Objective-Led, LLM-Powered Architecture

Replaces the old drag-and-drop step table with a clickable card-based layout,
brand voice system, LLM-generated previews, and per-template state management.

## Layout (top to bottom)

```
MAPPING STRIP (unchanged — Lead → Cadence rules)
3 TEMPLATE CARDS (unchanged — Cold | Inbound | Nurture)
├── 🎨 BRAND VOICE (per-template)
│   Tone: [Formal] [Warm & direct] [Casual] [Funny]
│   No-nos: ["Buzzwords"✕] [+ Add]
│   Formality: Casual ───○─── Formal  [1 2 3 4 5]
├───── 50/50 SPLIT ─────────────────────────────┤
│ LEFT                           RIGHT          │
│ 🎯 PRIMARY GOAL                ✨ PREVIEW     │
│ [text input]                   (LLM-generated │
│ 💬 WhatsApp  Day 0·+0h  ✕     when step      │
│   [objective input]            is clicked)    │
│ ✉️ Email     Day 1·+24h ✕     ⟳ Regenerate   │
│   [objective input]                           │
│ 📞 Call      Day 3·+48h ✕     🟢 REACHOUT   │
│   [objective input]           🔴 STOP         │
│ [+ Add Step]                   (side-by-side) │
└───────────────────────────────────────────────┘
```

## Key Architectural Decisions

### Config Screen (No Ava Chat)
The Cadence Builder is a **config screen** — it configures how outreach works.
No Ava chat panel on this page. Layout = `[sidebar 240px] [content-wrap flex:1]`
only. The all-in-one content-wrap uses a `.body-split` for its internal 50/50 layout.

### Per-Template State
Each template (Cold, Inbound, Nurture) has its own isolated state stored in
localStorage under key `ara_cadence_data`:

```javascript
{
  cold: {
    objective: "Book introductory discovery call...",
    brandVoice: { tone: "warm", nonos: [...], formality: 3 },
    steps: [
      { channel: "whatsapp", day: 0, delay: 0, desc: "Objective text..." },
      { channel: "email", day: 1, delay: 24, desc: "..." },
      ...
    ],
    conditions: { workingHours: true, weekdays: true, ... },
    stopConditions: { meetingBooked: true, optOut: true, ... }
  },
  inbound: { ... },
  nurture: { ... }
}
```

Template switching triggers an **unsaved changes prompt** — compare current DOM
values against the saved template data before switching.

### Brand Voice System

| Field | UI | Storage |
|-------|-----|---------|
| Tone | 4 chips (Formal, Warm & direct, Casual, Funny) | String `brandVoice.tone` |
| No-nos | Tag chips with ✕ delete + "+ Add" button | Array `brandVoice.nonos[]` |
| Formality | Range slider 1–5 | Number `brandVoice.formality` |

The no-nos container uses `+ Add` button at the end of the tag list. Deleting a
no-no removes the tag chip from the DOM. Adding prompts via `prompt()` dialog.

### Step Management

**Channel picker** — clicking "+ Add Step" opens a modal overlay with 4 options:
WhatsApp, Email, Call, SMS. Each option shows a styled icon + channel name.

**Step card** — each step is a clickable card with:
- Channel icon (WhatsApp green, Email blue, Call indigo, SMS gray)
- Channel name
- Delay display (e.g. "Day 0·+0h ✏️") — click to inline-edit day and hours
- Delete button (✕) — grey, turns red on hover
- Objective text input

**Delay editor** — clicking the delay span replaces it with inline day/hour
inputs + confirm (✓) button. Uses `data-action="edit-delay"` and `editDelay(index)`.

**Delete safety** — checks for minimum 1 step (can't delete last step).

### LLM-Powered Preview

The preview panel calls a backend endpoint:

```
POST /api/cadence/preview
{
  step: { channel, desc },
  brandVoice: { tone, nonos, formality },
  templateName: "Outbound (Cold Outreach)",
  leadName: "Rajesh",
  leadCompany: "Acme Manufacturing",
  leadCity: "Pune",
  leadIndustry: "manufacturing"
}
→ { preview: "LLM-generated message text..." }
```

**Backend** (`server.py`):
- Uses `call_llm()` from `induction_engine` (DeepSeek V4 Flash)
- Builds a system prompt from: channel, template name, tone, formality, no-nos
- Channel-specific format guidelines (WhatsApp=short+punchy, Email=subject+body,
  Call=talking-points outline, SMS=1-liner)
- Falls back to static `generate_fallback_preview()` if LLM fails

**Frontend**:
- Shows loading state "⏳ Generating preview..." while fetching
- Calls `fetch('/api/cadence/preview', ...)` on step select and regenerate
- Highlights `{{variable}}` placeholders with yellow background
- Fallback to `staticFallback(channel)` function on network error

### Conditions Layout

Conditions sit UNDER the preview in the right column, side-by-side:

```
┌─ 🟢 REACHOUT ─┬─ 🔴 STOP ──┐
│ ☑ Working hrs  │ ☑ Replied   │
│ ☑ Weekdays     │ ☑ Opted out │
│ ☐ Saturday     │ ☐ Not int.  │
│ ☐ Sunday       │              │
└────────────────┴─────────────┘
```

Each condition card uses `.cond-card { flex: 1 }` inside `.cond-inline { display: flex; gap: 12px; }`.
Stop conditions get red text via `.cond-row.stop .cond-label { color: #C62828; }`.

### Publish Flow

"Publish Cadence" button calls `saveCurrentState()` then shows a toast:
"✅ Cadence published — [template name] saved and activated".

"Reset to Default" shows a confirm dialog, then restores `DEFAULT_TEMPLATES[currentTemplateId]`
for that specific template only.

## Pitfalls

### `t.steps = []` — Step Wipe Bug
The `saveCurrentState()` function MUST NOT set `t.steps = []`. The old code had:
```javascript
var stepCards = document.querySelectorAll('#stepsContainer .step-card');
t.steps = [];  // ← BUG: wipes all step channel/day/delay data
```
Fix: Only update descriptions from DOM, never reassign the steps array.
The channel, day, and delay are already in the in-memory template data.

### localStorage Corrupted Data Recovery
If `saveCurrentState()` previously saved empty steps (from the bug above),
`loadData()` needs a recovery path:
```javascript
// Restore steps if wiped by prior bug
if (!data[key].steps || data[key].steps.length === 0) {
  data[key].steps = JSON.parse(JSON.stringify(DEFAULT_TEMPLATES[key].steps));
}
```

### Event Delegation for Cadence Builder
The Cadence Builder uses a single `document.addEventListener('click', ...)` with
`data-action` attributes. Action types:
- `select-template` — template card
- `select-step` — step card click
- `edit-delay` — delay span click
- `delete-step` — ✕ button
- `edit-objective` — objective input (handled by input event, not click)

Default step presets:
- Cold: WhatsApp (D0,+0h) → Email (D1,+24h) → Call (D3,+48h) → WhatsApp (D5,+48h)
- Inbound: Email (D0,+0h) → Call (D1,+24h) → WhatsApp (D3,+48h)
- Nurture: Email (D0,+0h) → Email (D3,+72h) → Call (D7,+96h)
