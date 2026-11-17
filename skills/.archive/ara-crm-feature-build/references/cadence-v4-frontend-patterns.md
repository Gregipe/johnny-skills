# Cadence Builder v4 — Frontend Patterns

This session (May 27, 2026) produced several important frontend patterns for the cadence builder and related pages.

## Single Textarea Per Step

v4 simplified from two textareas (desc + channelPrompt) to one. The user writes everything in one prompt.

**Step card rendering pattern:**
```javascript
'<textarea class="step-desc" data-step-index="' + i + '" placeholder="Write the full message prompt for this step. Include what to say, channel-specific guidance, personalization cues, and the CTA.">' + descText.replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</textarea>'
```

**Step object shape:**
```javascript
{channel: 'whatsapp', delay_hours: 0, repeat_count: 1, interval_hours: 0, desc: '...'}
```
No `channelPrompt` field. Removed from all: DEFAULT_TEMPLATES, saveCurrentState, addStep, renderSteps, and the backend `_generate_step_message`.

**Real-time desc save (via input listener):**
```javascript
document.addEventListener('input', function(e) {
  if (e.target.classList.contains('step-desc')) {
    var idx = parseInt(e.target.dataset.stepIndex);
    var t = getTemplate();
    if (t && t.steps[idx]) {
      t.steps[idx].desc = e.target.value;
      saveData();
    }
  }
});
```

## "channel prompt" Grey Label

A small visual hint in each step card header. 8px grey text between the step name and timing.

**HTML (inside step-top):**
```javascript
'<span class="step-ch">channel prompt</span>'
```

**CSS:**
```css
.step-ch { font-size:8px; color:#B0B0B5; font-weight:500; letter-spacing:.2px; margin-right:4px; white-space:nowrap; flex-shrink:0; }
```

## Step Picker — SMS Removed

The channel picker modal now only shows WhatsApp, Email, and Call.

**Picker chips (grid of 2 columns × 2 rows):**
```html
<!-- WhatsApp | Email -->
<!-- Call    | (empty — no SMS) -->
```

## 3-Channel Defaults Per Cadence

All three cadences (cold, inbound, nurture) pre-loaded with exactly WhatsApp → Email → Call.

```javascript
cold:     [{channel:'whatsapp', delay_hours:0},  {channel:'email', delay_hours:4},  {channel:'call', delay_hours:48}]
inbound:  [{channel:'email', delay_hours:0},     {channel:'call', delay_hours:24}, {channel:'whatsapp', delay_hours:48}]
nurture:  [{channel:'email', delay_hours:0},     {channel:'email', delay_hours:72},{channel:'call', delay_hours:168}]
```

Note: nurture uses 2 emails + 1 call since that cadence type needs more touches.

## System Prompt Persistence — Two Fixes

**Migration fix:** `if (!data[key].systemPrompt)` → `if (data[key].systemPrompt === undefined)`
Empty string must not trigger default override.

**Change event handler:**
```javascript
document.addEventListener('change', function(e) {
  if (e.target.id === 'systemPromptInput') {
    var t = getTemplate();
    if (t) { t.systemPrompt = e.target.value; saveData(); }
  }
});
```

## Unsaved Changes Warning

```javascript
window.addEventListener('beforeunload', function(e) {
  if (hasUnsavedChanges) {
    e.preventDefault();
    e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
    return 'You have unsaved changes. Are you sure you want to leave?';
  }
});
```

Covers: refresh, tab close, back/forward, sidebar nav clicks. The `hasUnsavedChanges` flag is set by `markUnsaved()` on any input change, cleared by `saveCurrentState()`.

## Primary Goal Box Removal

The `🎯 Primary Goal` input was removed. The cadence objective goes as the first line of the system prompt.

Removed from: HTML (`goal-card` div), `saveCurrentState()` (`t.objective = ...`), `renderCurrentTemplate()` (`goalInput.value = ...`), `checkUnsaved()`, input handler, change event handler, and CSS (`.goal-card`, `.goal-label`, `.goal-input`).

## Lead Chat Message Formatting

When starting a chat about a lead, the initial user message now uses structured text with emojis and box-drawing characters:

```javascript
var msg = "📋 Lead: " + data.lead_name + " — " + (data.lead_company || "") + "\n" +
  "━━━━━━━━━━━━━━━━━━━━━━━━━━\n" +
  "• Name:    " + data.lead_name + "\n" +
  "• Company: " + (data.lead_company || "N/A") + "\n" +
  "• Phone:   " + (data.lead_phone || "N/A") + "\n" +
  "• Email:   " + (data.lead_email || "N/A") + "\n" +
  "• Source:  " + (data.lead_source || "N/A") + "\n" +
  "• Stage:   " + (data.lead_stage || "new") + "\n" +
  "• Notes:   " + (data.lead_notes || "None") + "\n" +
  "━━━━━━━━━━━━━━━━━━━━━━━━━━\n" +
  convText + "\n\n" +
  "Summarize this lead and their recent activity in 2-3 sentences.";
```

**Critical `\n` escaping:** In JavaScript source files, always use `"\n"` (single backslash-n) for actual newlines in `textContent`-rendered strings. Using `"\\n"` (double backslash) produces a literal `\n` string that shows as visible characters in the chat. The `white-space: pre-wrap` CSS on `.chat-msg` renders `\n` as line breaks.

This applies to ALL JavaScript files, not just Python-embedded ones. The common mistake is `"\\\\n"` in Python template strings (which produces `\\n` in the JS output → literal `\n`). See `references/python-js-escaping.md` for the full debugging workflow.

## Sidebar Consistency Between Pages

Every standalone page (threads, cadence, dashboard) must have an IDENTICAL sidebar HTML. The canonical source is the cadence page sidebar in `server.py` (around line 1830+).

**Key elements:**
- Logo: `AR` (not `ARA`) in a 36px black square
- Title: `Autonomous<br>Revenue Agent <span>v1.0</span>`
- Nav sections: Main, Intelligence, Learning, Configuration (with `.nav-section-title` labels)
- All 12 nav items (Home, Leads, Deals, Activities, Actions, Outreach Central, Knowledge Base, Induction, Learnings, Integrations, Threads)
- Active state on the current page's nav item
- Footer: Greg / Business Lead · Hunar.ai with avatar

**CSS requirements (per page, if inheriting from a different template):**
```css
.nav-section{margin-bottom:8px}
.nav-section-title{padding:6px 10px 4px;font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.6px;color:#9A9A9E}
.sidebar-footer{padding:12px 8px;border-top:1px solid #E5E5E7}
.sidebar-user{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;cursor:pointer}
.sidebar-user:hover{background:#E8E8ED}
.sidebar-user .avatar{width:28px;height:28px;border-radius:50%;background:#D0D0D5;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;color:#6E6E73}
.sidebar-user .info .name{font-size:13px;font-weight:600;color:#111}
.sidebar-user .info .role{font-size:11px;color:#6E6E73}
```

**JS functions required:**
```javascript
function showIntegrations() { window.location.href = '/dashboard#integrations'; }
```

**Rule:** When copying the sidebar between pages, copy the COMPLETE HTML block — don't selectively update items. Partial updates miss new items or structural changes.
