---
name: ara-cadence-logic
description: ARA cadence pipeline — stage advancement, qualification, disqualification, meeting booking, dormant re-engagement, silence resume, channel switching, post-engagement agentic behavior, and system-prompt-first message generation (system prompt rules supreme for WhatsApp & email; step desc is auto-generated fallback).
---

# ARA Cadence Logic Implementation

## System Awareness Tools (June 2026)

Ava has two tools for discovering system state dynamically instead of relying on hardcoded prompt text:

### Tool: `get_system_map` (tool #29)
- **Args:** `{}` (none)
- **Returns:** UI navigation URLs, cadence object model, and LIVE published configs for ALL templates
- **Handler:** `server.py` — `execute_tool()` at lines ~3636
- **Use case:** When Greg asks "where do I configure X" or "what's configured right now"

### Tool: `get_cadence_config` (tool #30)
- **Args:** `{"template_id": "cold|inbound|nurture"}`
- **Returns:** Full published config for one template — steps, conditions, brandVoice, stopConditions
- **Handler:** `server.py` — `execute_tool()` at lines ~3690
- **Use case:** Faster than get_system_map when Greg asks about a specific cadence

### Origin: Durable Over Static Prompt
Initially a 30-line "## System Architecture" section was hardcoded into `AGENT_SYSTEM_PROMPT_BASE` listing UI URLs, object model, and how-to-guides. Greg rejected this: "next time always use tools."

See also `references/diagnostic-tools.md` for read_logs and debug_schedule tool details.

**Fix:** Replaced the static prompt with two tools + a 5-line instruction telling Ava to call them. Tools query the DB live — never stale, no prompt edits needed when the system changes.

### Critical: UnboundLocalError Pattern (Two Instances)
Python marks ALL names from function-level imports as local for the entire function. If a different code path references the name before the import-executing branch runs, it raises `UnboundLocalError`.

**Instance 1 (May 30):** `from database import Conversation` inside `get_summary()` handler — crashed `get_lead_detail()` because `Conversation` was read before `get_summary()` ever executed.

**Instance 2 (June):** `import json` inside `mark_meeting_booked` handler (line ~3237) — crashed `get_system_map` and `get_cadence_config` because `json.dumps()` was called before the `mark_meeting_booked` branch ever executed.

**Instance 3 (also June, same session):** `from database import IntegrationConfig` at line ~306 inside `mark_meeting_booked` — shadows module-level `IntegrationConfig`. Same pattern, same fix.

**Fix for all:** Remove the local import — the name is already at module level. After fixing, grep for all `from database import X` inside `execute_tool()` to catch any remaining shadowing instances.

**Verification:** After fixing one, check the full function body for other local imports that shadow module-level names:
```bash
cd /Users/greg/ara && sed -n '/def execute_tool/,/AGENT_SYSTEM_PROMPT_BASE/p' server.py | grep -n 'from database import\|^import '
```

### Global Prompt Publish Bug (June 2026)
**The bug:** `savePromptAndClose()` in `cadence_template.py` publishes the compiled prompt with `template_id: 'global'` to `/api/cadence/publish`. But the backend only accepts `template_id in ("cold", "inbound", "nurture")`. The publish silently fails — the frontend shows "Saved locally" but the DB never receives `systemPrompt` or `promptParts`.

**Result:** When the scheduler fires an email, `_generate_step_message()` reads `config.get("systemPrompt", "")` which returns empty string. The LLM generates from bare brandVoice + step desc + channel guide — no Hunar.ai positioning, no value props, no customer names. Emails come out generic and poorly written.

**Fix:** Added `POST /api/cadence/publish-global` endpoint that accepts `{promptParts, compiled_prompt}` and writes both to ALL three templates (cold, inbound, nurture) in one call. Updated `savePromptAndClose()` to call this endpoint instead of the old `template_id: 'global'` pattern.

**publishCadence fan-out (June 2026):** The main "Publish Cadence" button on the cadence page now also calls `publish-global` if the template has a compiled systemPrompt (>50 chars). This means a single Publish click saves steps/conditions AND fans out the global prompt to all three templates:

```javascript
function publishCadence() {
  saveCurrentState();
  var t = getTemplate();
  // ...publish steps/conditions for THIS template...
  fetch('/api/cadence/publish', {
    body: JSON.stringify({ template_id: t.id, template: t })
  })
  .then(function(data) {
    if (data.status === 'ok') {
      // Also publish global prompt to ALL templates
      if (t.systemPrompt && t.systemPrompt.length > 50) {
        var parts = globalPromptParts || t.promptParts || {};
        fetch('/api/cadence/publish-global', {
          body: JSON.stringify({ promptParts: parts, compiled_prompt: t.systemPrompt })
        }).catch(function() {});  // fire-and-forget
      }
      showToast('✅ Published');
    }
  });
}
```

**How the prompt reaches the server (two paths):**
- **Save & Close** in Prompt Builder → calls `/api/cadence/publish-global` directly
- **Publish Cadence** on main page → publishes template + also calls `/api/cadence/publish-global` if prompt exists

**Verification:** Check DB for populated `systemPrompt`:
```bash
sqlite3 ara.db "SELECT template_id, length(COALESCE(json_extract(config, '$.systemPrompt'), '')) as sysprompt_len FROM cadence_configs;"
```

### Debugging Bad Outbound Emails
When Greg reports a poorly written email from the cadence:

1. **Check if `systemPrompt` is populated in DB:**
   ```bash
   sqlite3 ara.db "SELECT template_id, json_extract(config, '$.systemPrompt') IS NOT NULL AS has_sysprompt, length(COALESCE(json_extract(config, '$.systemPrompt'), '')) AS len FROM cadence_configs;"
   ```
   If `len` is 0 for all templates → the global prompt was never published to the backend. Greg needs to open `/cadence`, click "✎ Open Builder", and "Save & Close" to publish.

2. **Check the step descs** — if they're too generic (e.g. "Cold email sequence x12") the LLM has nothing specific to work with.
   - **Fix:** Replace with the full channel prompt from `promptParts.channelSpecific[channel]`. See the ⚠️ section under "Message Content Generation Architecture" above.

3. **Check brandVoice** — if nonos are too narrow, the LLM can find workarounds (e.g. nono says "I wanted to reach out" but LLM writes "I wanted to share" instead).


## Entry Points

| What | Where |
|------|-------|
| **Cadence Builder UI** (edit steps, publish templates) | `http://localhost:8766/cadence` |
| **Cadence Config API** (publish/validate/load) | `POST /api/cadence/publish`, `GET /api/cadence/config`, `POST /api/cadence/validate` |
| **Trigger cadence for a lead** (restart) | `POST /api/cadence/trigger/lead/{lead_id}` |
| **Pause cadence for a lead** | `POST /api/cadence/pause/lead/{lead_id}` |
| **Bulk trigger** (all leads by stage) | `POST /api/cadence/trigger` |

When a user asks "where do I modify the cadence steps" — point them to `/cadence`. That's the full drag-drop SPA in `cadence_template.py`.

## Architecture

Hybrid approach: **code-enforced mechanics** + **LLM-judged evaluation** + **parameterized config**.

- **Stage transitions, scheduling gates, action cancellation** → Code in `server.py`
- **Qualification, intent detection, re-engagement classification** → LLM-judged via tools
- **Timing/thresholds** → Tenant `config` JSON field

## Stage Pipeline

```
new → reached_out → engaged → qualified → meeting_booked → [HUMAN TAKES OVER]
                    ↑               ↓
                dormant ←──────── lost
```

## What was built

### 1. `engaged → qualified` Advancement
**File:** `server.py` — `execute_tool()` handler for `evaluate_qualification`

- **Tool signature:** `{"tool": "evaluate_qualification", "args": {"lead_name": "...", "assessment": "...", "fits_icp": true/false/"uncertain", "confidence": "high/medium/low"}}`
- **Logic:**
  - `fits_icp=true + confidence=high` → auto-advance to `qualified`, create ActionItem with ✅ title
  - `fits_icp=true + confidence=medium` → advance to `qualified`, flag for human review with 🔔 title  
  - `fits_icp=false + confidence=high/medium` → move to `lost`, cancel all pending actions, create 🚫 ActionItem
  - `confidence=low` → don't change stage, create ❓ ActionItem for human review
  - Always calls `_sync_deal_stage_from_lead()` on advancement
- **Rule:** Be BROAD — only disqualify on complete mismatch. KBs/skills loaded for context but not required.

### 2. Meeting Booking Detection
**File:** `server.py` — `execute_tool()` handler for `mark_meeting_booked`

- **Tool signature:** `{"tool": "mark_meeting_booked", "args": {"lead_name": "...", "meeting_details": "Thursday 3pm, demo call"}}`
- **Logic:** Moves lead to `meeting_booked`, cancels all pending actions, syncs deal stage, creates 📅 ActionItem for human notification
- **Rule:** Only use when lead explicitly agrees to meet. "Call me later" ≠ meeting. Ava's ceiling — human takes over after.

### 3. Scheduling Gate — Engaged+ Exclusion
**File:** `server.py` — `_schedule_cadence_for_lead()`

- Changed skip list from `("qualified", "meeting_booked", "dormant")` to `("engaged", "qualified", "meeting_booked", "dormant", "lost", "closed_lost", "closed_won")`
- Once a lead hits `engaged`, no more template cadence steps. Ava handles them agentically.

### 4. Disqualification Handling (`lost` stage)
**File:** `server.py`

- `update_lead()` — when stage changed to `lost`, auto-cancel all pending ScheduledActions
- `_check_dormant()` — exclude `lost`, `closed_lost`, `closed_won` from auto-dormant marking
- `_handle_inbound_whatsapp()` — lost leads re-engaging get flagged for human review, not auto-advanced

### 5. Smart Dormant Re-engagement
**File:** `server.py` — `_handle_inbound_whatsapp()`

- `new/reached_out` → `engaged` (unchanged)
- `dormant` → Check if lead had a deal at `qualified`/`meeting_booked`:
  - Yes → restore to `qualified`, create ActionItem indicating re-engagement
  - No → restore to `engaged`
- `lost` → Flag for human review (ActionItem `review_reengagement`), don't auto-respond without Greg's approval

### 6. 7-Day Silence Resume Protocol
**File:** `server.py` — `_check_silence_resume()`

- Runs in scheduler loop alongside `_check_dormant()`
- Polls all `engaged`/`qualified` leads for activity in last 7 days
- If silent AND no pending follow-up → schedule a dignified check-in
- Channel alternation: email → WhatsApp → email → WhatsApp (based on previous 30-day follow-up count)
- Fires within 1 hour via `ScheduledAction`
- Message template: friendly, low-pressure ("any thoughts since we last spoke")

### 7. Prompt Updates
**File:** `server.py`

- `AVA_AUTO_SYSTEM_PROMPT` (WhatsApp auto-response) — Added "After-Conversation Actions" and "Channel Switching" sections
- `AGENT_SYSTEM_PROMPT_BASE` (dashboard chat) — Added "Post-Engagement Behavior" section
- `AGENT_TOOL_SCHEMA` — Added tools 12 (`evaluate_qualification`) and 13 (`mark_meeting_booked`) with descriptions and examples

### 8. New Ava Tools
**File:** `server.py` — `execute_tool()` and `AGENT_TOOL_SCHEMA`

| Tool | Args | What it does |
|------|------|-------------|
| `evaluate_qualification` | lead_name, assessment, fits_icp, confidence | Advanced/disqualify/review based on LLM judgment |
| `mark_meeting_booked` | lead_name, meeting_details | Marks meeting, stops cadences, notifies human |

## Built-in vs Ava-called

- **Code-enforced:** Scheduling gates, `lost`→cadence cancellation, dormant auto-detection, 7-day silence check
- **LLM-judged:** `evaluate_qualification`, `mark_meeting_booked` — Ava decides when to call these
- **Configurable (future):** Silence threshold (7d), email frequency, channel preferences — in tenant `config` field

### 9. Giving Ava System-Architecture Awareness (May 2026)

**Problem:** When Greg asked Ava "where in the system can I modify the outbound steps?", she responded "I don't have visibility into the system's backend UI or admin panel." This was frustrating because:
- The cadence config IS published in the DB
- The UI IS accessible at `/cadence`
- Ava just doesn't know about it

**Pattern:** Add a `## System Architecture` section to the agent's system prompt (`AGENT_SYSTEM_PROMPT_BASE` in `server.py`) that tells Ava:

1. **UI Locations** — a map of routes Greg uses (Dashboard `/`, Cadence Builder `/cadence`, Deals `/deals`, Induction `/induction`, Actions `/actions`)
2. **Object Model** — the data structures (steps, channels, delay_hours, repeat_count, interval_hours, desc, conditions, brandVoice, systemPrompt)
3. **How to Guide Greg** — specific playbooks for common questions ("Where do I edit steps?" → point to Cadence Builder at /cadence)

**Where to put it:** Only in `AGENT_SYSTEM_PROMPT_BASE` (the dashboard agent prompt — Greg-facing). Do NOT add to `AVA_AUTO_SYSTEM_PROMPT` (WhatsApp auto-responder — customer-facing, leads don't need to know about internal UI).

**When the user asks this kind of question:** The class of work is "giving an AI agent contextual awareness of the system it operates in." The fix is always in the system prompt — add a structured section describing the system's UI, data model, and guidance for answering user questions about it. The three-component structure (UI map + object model + how-to-guide) is reusable across any agent that needs to answer "where do I edit X?" questions.

**File modified:** `server.py` — `AGENT_SYSTEM_PROMPT_BASE` at line ~3677 (after "## Post-Engagement Behavior" section)

### 10. ActionItems Notification System (Human Task Inbox)

**What:** Human-facing notifications created by `evaluate_qualification`, `mark_meeting_booked`, dormant re-engagement, lost-lead re-engagement, and `_check_and_create_action_items()`.

**DB Table:** `ActionItem` — `id`, `tenant_id`, `action_type`, `title`, `description`, `ref_type`, `ref_id`, `status` (open/dismissed/resolved), `created_at`, `resolved_at`

**API Endpoints:**
- `GET /api/action-items` — list (defaults to open; `?status=all` for everything)
- `GET /api/action-items/stats` — counts by status for badge
- `PATCH /api/action-items/{id}` — update status (`{"status": "resolved"}` or `"dismissed"`)

**Action Types:** `stage_change`, `review_qualification`, `meeting_request`, `suggest_deal`, `escalate`, `review_reengagement`, `review_lead`

**Dashboard:** Actions page (`renderActions()` in `static/dashboard.js`) fetches from `/api/action-items`, resolves lead names, renders cards with type-specific icons + ✓ Done button. Filter pills for Open/All/Resolved/Dismissed.

### 10. Three-Tier Activity Model (Conceptual Framework)

| View | What | Backend | Badge |
|------|------|---------|-------|
| **Activities** | Chronological system log — lead conversations + scheduled outbounds | `/api/activities` (conversations) + `/api/actions?upcoming=true` (outbound schedule) | None |
| **Actions** | Human task inbox — things Greg needs to review/decide | `/api/action-items` | Red badge = open count |
| **Scheduled Outbounds** (subsection of Activities) | Upcoming automated messages Ava will send | `/api/actions?upcoming=true` | None |

**Key distinction:** Activities = WHAT THE SYSTEM IS DOING. Actions = WHAT THE HUMAN NEEDS TO DO. These are semantically separate and must never be mixed.

**Badge rule:** The red badge on the Actions nav item counts **open ActionItems only** — never upcoming scheduled actions. Badge polls `/api/action-items/stats` every 15s.

For dashboard integration details, see `references/actionitems-notification-system.md`.

### 11. Message Content Generation Architecture (Live — May 2026)

Generates compelling message content at send time using a **two-layer prompt hierarchy** — no pre-interpolated templates.

#### Email Signature Format (June 2026)

The email channel prompt now includes explicit signature guidance:

```
## Signature
First email in a thread: sign with full name, title, and company
  — e.g. "Ava — Business Lead, Hunar.ai"
Follow-up replies in the same thread: just your first name
  — "Ava"
```

**Where it lives:** In `promptParts.channelSpecific.email.body` — the email body section of the channel prompt. It was added as a `## Signature` subsection in the body text.

**Also in compiled system prompt:** A `**Signature**` line was added to the email rules section of the compiled `systemPrompt` for all three templates (fanned out via `publish-global`).

**WhatsApp already had:** `Signature: Just your first name, no need for full email signature.` (no change needed — WhatsApp always uses just "Ava").

**Verification:**
```bash
cd /Users/greg/ara && python3 -c "
import json, sqlite3
db = sqlite3.connect('ara.db')
for t in ['cold','inbound','nurture']:
    row = db.execute(\"SELECT config FROM cadence_configs WHERE template_id=?\", (t,)).fetchone()
    cfg = json.loads(row[0])
    body = cfg.get('promptParts',{}).get('channelSpecific',{}).get('email',{}).get('body','')
    print(f'{t}: Signature in body={\"## Signature\" in body}')
    sp = cfg.get('systemPrompt','')
    print(f'{t}: Signature in sysprompt={\"**Signature**\" in sp}')
"
```

**Pitfall:** When adding signature guidance, ensure it's added to BOTH the promptParts.channelSpecific.email.body (used by Prompt Builder UI & compilation) AND the compiled systemPrompt (used by LLM at send time). Publish-global propagates the compiled prompt to all templates, but you must also update promptParts in the DB for each template if editing directly.

### ⚠️ Critical: Step desc MUST be the full channel prompt, not a summary (June 2026)

**Failure mode:** Greg created 8 WhatsApp + 12 email steps in the cold cadence, with rich channel prompts in the Prompt Builder (`promptParts.channelSpecific.whatsapp` and `.email` — 1,333 and 1,798 chars respectively). But the step `desc` field contained only a one-line summary:

```
"Cold WhatsApp sequence x8. Reference growth, lead with compliment, 2-3 lines."
"Cold email sequence x12. Reference screening bottleneck, 3-4 paragraphs."
```

When Ava tried to send messages, she operated on the thin one-liner — the rich channel prompts were sitting unused in `promptParts.channelSpecific`. The LLM had no sequencing guidance, no tone rules, no subject line format, no case study references. Emails came out generic.

**Root cause:** The `desc` field is what the LLM sees as `## Step Objective`. The `promptParts.channelSpecific` data is only used by the Prompt Builder UI and the compile/validation pipeline — it is NOT automatically wired into the step desc at send time. There's no auto-copy mechanism. The user must manually set the step desc to the channel prompt content.

**Fix (workflow, not code):** When setting up cadence steps, populate each step's `desc` with the FULL corresponding channel prompt text from `promptParts.channelSpecific[channel]`. The channel prompts already contain structure, sequencing (Message 1/2/3 rules), tone guidance, subject line rules, CTA formats, and timing — everything the LLM needs.

**Where the channel prompts live:** In the Prompt Builder, tabs WhatsApp, Email, Call. Each is a free-form textarea. The text IS what the LLM needs for that channel's messages.

**Verification that descs are rich enough:**
```bash
cd /Users/greg/ara && python3 -c "
import json, sqlite3
db = sqlite3.connect('ara.db')
row = db.execute(\"SELECT config FROM cadence_configs WHERE template_id='cold'\").fetchone()
cfg = json.loads(row[0])
for s in cfg.get('steps', []):
    desc = s.get('desc','')
    print(f'{s[\"channel\"]}: {len(desc)} chars — first: {desc[:60]}...')
"
# Expected: 1000+ chars per step, starting with '## WhatsApp Structure...' or '## Email Subject Line...'
```

**If a step desc is < 100 chars and the channel prompt exists in promptParts:** The step was configured with a summary instead of the full channel prompt. Replace it via DB update (step desc textarea was removed from the UI in June 2026).

### Step Desc UI Removal & LLM Gate Fix (June 2026)

**What changed:** The step `desc` textarea was **removed from the cadence builder UI**. The user determined that since step descs are populated from the channel prompts in the Prompt Builder, the textboxes serve no purpose.

**Implied backend fix:** See `references/cadence-scheduling-llm-gate-fix-june2026.md` for the full fix — the scheduling gate was changed from desc-based to channel-based (`if channel in ("whatsapp", "email"):` replaces `if desc and not fields:`), and `_generate_step_message` now auto-generates a positional fallback desc instead of returning None.

**What was removed from `cadence_template.py`:**
1. **CSS** — `.step-desc` and `.step-desc:focus` rules
2. **Textarea** — `<textarea class="step-desc">` line in `renderSteps()`
3. **Save handler** — `// Read desc from textarea` block in `saveCurrentState()`
4. **Unused variable** — `var descText = s.desc || '';`
5. **Click guard** — `TEXTAREA` removed from the `select-step` tagName check
6. **Real-time save** — `.step-desc` input change tracking and auto-save removed from the `input` listener

**Current step card layout:**
```
[⠿] [1] [icon] WhatsApp  channel prompt  Fire after [0]h × [8] times × every [1]h [✕]
```

Only timing controls (delay_hours, repeat_count, interval_hours) remain editable per step in the UI. The `desc` field still exists in the data model and is sent to the LLM — it's populated from the channel prompt content and cannot be manually edited in the UI.

**When adding new steps:** `addStep()` creates steps with `desc: ''`. The channel prompt content from `promptParts.channelSpecific[channel]` should be used to populate it. For existing setups, the descs must be set via DB update. New steps are added via the dynamic channel picker (see "Add Channel Dynamic Picker" below).

**Rule:** When setting up cadence steps, populate each step's `desc` with the FULL corresponding channel prompt text from `promptParts.channelSpecific[channel]`. The channel prompts already contain structure, sequencing, tone guidance, subject line rules, CTA formats, and timing — everything the LLM needs. There is NO manual edit path in the UI for step descs.

### Add Channel Dynamic Picker (June 2026)

**### Channel Picker (formerly Step Picker)**

**Available channels:** whatsapp (WhatsApp), email (Email), call (Call), sms (Text)

**Picker logic:** `renderStepPicker()` in `cadence_template.py`:
1. Collects all channel IDs already present in `t.steps`
2. Filters from the 4 available channels to show only unused ones
3. If all 4 are in use, shows "All 4 channels already configured" message
4. If none configured, all 4 are offered

```javascript
function renderStepPicker() {
  var t = getTemplate();
  var used = {};
  (t.steps || []).forEach(function(s) { used[s.channel] = true; });
  var ALL = [
    { id:'whatsapp', name:'WhatsApp', icon: CHANNEL_ICONS.whatsapp },
    { id:'email',    name:'Email',    icon: CHANNEL_ICONS.email },
    { id:'call',     name:'Call',     icon: CHANNEL_ICONS.call },
    { id:'sms',      name:'Text',     icon: CHANNEL_ICONS.sms }
  ];
  var available = ALL.filter(function(ch) { return !used[ch.id]; });
  // ... render chips or "all configured" message
}
```

**UX behavior:**
- "Add Channel" button opens the picker overlay via `openStepPicker()` which first calls `renderStepPicker()` then shows the overlay
- Each available channel renders as a `.picker-chip` with icon + name
- Clicking a chip calls `addStep(channel)` → pushes `{channel, delay_hours:0, repeat_count:1, interval_hours:0, desc:''}` to steps
- New steps start with empty desc (must be populated from channel prompts via DB update)
- "Cancel" dismisses the modal without adding

**Picker overlay HTML** (static, in `cadence_template.py` before the confirm dialog):
```html
<div class="picker-overlay" id="stepPickerOverlay">
  <div class="picker-modal">
    <h3 id="pickerTitle">Add Channel</h3>
    <div class="picker-channels" id="pickerChannels"></div>
    <div class="picker-close" onclick="closeStepPicker()">Cancel</div>
  </div>
</div>
```

**CSS** for the picker (already existed for `picker-overlay`, `picker-modal`, `picker-channels`, `picker-chip`, `picker-close` classes — the overlay HTML was missing and was added in this session).

**Naming changes:** "SMS" was renamed to "Text" in `CHANNEL_NAMES` to match user preference: `{ whatsapp:'WhatsApp', email:'Email', call:'Call', sms:'Text' }`.

**Pitfall:** The `addStep()` function does NOT auto-populate `desc` from the channel prompt. New steps have `desc: ''`. For the LLM to generate quality content, the desc must be populated with the full channel prompt text. This requires a DB update to set `promptParts.channelSpecific[channel]` content into the step desc for any newly added channel.

### Prompt Layers

```
System Prompt  ← Ava-generated, Greg-editable
  Brand voice, positioning, competitive intel, industry context, guardrails.
  Inherited by ALL steps in the cadence.
  This is the ONLY per-template prompt field.

Step Desc  ← Greg-authored per step
  Rich NL prompt describing what to communicate, channel guidance, personalization cues, CTA.
  ONE textarea per step — user includes channel constraints directly
  (e.g. "Short and warm, 2-3 lines for WhatsApp" / "3-4 paragraphs with subject line for email").

Built-in Channel Guide (hardcoded in _generate_step_message, not configurable):
  WhatsApp: "Short, punchy (2-3 lines max). Use emojis sparingly. No formal salutation."
  Email:    "Include a subject line. 3-4 paragraphs max. Professional sign-off."
  Call:     "Provide talking points as a structured outline, not a script."
```

### Step Data Model

Each step stores a single rich NL prompt plus timing:

```json
{
  "channel": "whatsapp",
  "delay_hours": 0,
  "repeat_count": 1,
  "interval_hours": 0,
  "desc": "Cold WhatsApp. Reference their recent growth/expansion. Lead with a specific compliment. Warm, direct, 2-3 lines. CTA: '2 minutes to see if it fits?'"
}
```

**No channelPrompt field** — merged into desc. The built-in channel_guide handles channel formatting automatically. **The step desc textarea was removed from the UI in June 2026** — descs are populated from channel prompts only, not manually editable per step.

**Channel options:** WhatsApp, Email, Call, and Text (stored as `sms`). The dynamic Add Channel picker shows only channels not yet configured for the current cadence.

**Timing model (replaces old `day`+`delay`):**
| Field | Description |
|-------|-------------|
| `delay_hours` | First fire offset from lead creation (in hours) |
| `repeat_count` | How many times to send this step (default 1) |
| `interval_hours` | Gap between repeats (default 0) |

Each step schedules `repeat_count` actions starting at `delay_hours`, spaced by `interval_hours`. Repeats **cascade** — each repeat's fire time is calculated from the previous repeat's adjusted time, not independently from `now`. This prevents working hours constraints from collapsing all repeats to the same slot.

**Cascade logic (May 2026 fix):**
```python
fire_at = now + timedelta(hours=delay_hours)
for r in range(repeat_count):
    if channel in ("email", "call"):
        fire_at_adj = _next_working_time(fire_at, conditions)
    else:
        fire_at_adj = fire_at
    
    # ... create ScheduledAction with scheduled_at=fire_at_adj ...
    
    fire_at += timedelta(hours=interval_hours)
```

**Before the fix:** `fire_at = now + timedelta(hours=delay_hours + r * interval_hours)` computed each repeat independently from `now`. When working hours pushed the first email to Monday 9AM, all subsequent emails (also computed from `now`) landed at the same Monday 9AM because they were all weekend/after-hours times.

**After the fix:** The first email lands on Monday 9AM. The second is computed from that adjusted time + 1h = Monday 10AM. Third = Monday 11AM, etc. Emails spread correctly across the working day.

**Pitfall:** Setting `delay_hours` too high relative to working hours can cause the first repeat to land after 6PM. With `workingHours: true`, it pushes to next day 9AM. If that next day is a blocked weekend day, it pushes to Monday. ALL subsequent repeats then cascade from Monday, wasting the lead's weekend window. Solution: set `delay_hours=0` when you want messages to start immediately and let working hours naturally constrain them.

**Channel options:** WhatsApp, Email, Call, and Text (stored as `sms` in the data model). All four are available in the dynamic Add Channel picker.

**Default 3-channel setup:** All three cadences pre-loaded with WhatsApp → Email → Call. Default timings vary by cadence type. Users can delete or reorder.

### At Send Time

`_execute_action()` detects `_format:"llm"` in the payload and calls `_generate_step_message()` which:

1. Loads cadence template's `systemPrompt`
2. Loads step's `desc` (rich NL prompt — channel guidance inline)
3. Applies built-in `channel_guide` dict
4. Injects lead context (name, company, industry, city, stage, source)
5. Injects sequence position: "This is step N of M in the sequence."
6. **Injects repeat context** for multi-send steps: "This specific message is send X of Y for this step." — stored as `_repeat_idx` and `_total_repeats` in the payload (set by `_schedule_cadence_for_lead()`, extracted by `_execute_action()`, passed to `_generate_step_message()`)
7. Adds instruction: "Vary the content naturally from previous sends — don't repeat the same angle or phrasing."
8. Calls LLM → generates exact message text → sends via the appropriate channel

### Language Constraint (Critical)

The LLM (DeepSeek, etc.) may detect the language of the lead/context and switch to a non-English language in its output. **This happens even when the user communicates in English** — the model can pick up regional cues from lead names, city names, or the user's accent/writing style.

**Fix:** Add an explicit language instruction at the VERY TOP of every system prompt — before any role definition, lead context, or instructions:

```
You ALWAYS respond in English, regardless of the language the user writes in.
```

**Apply to ALL three prompt locations:**
- `AGENT_SYSTEM_PROMPT_BASE` — agent chat (Greg chatting with Ava)
- `AVA_AUTO_SYSTEM_PROMPT` — WhatsApp auto-responder (leads)
- `INDUCTION_SYSTEM_PROMPT` — induction coach (if used for customer-facing chat)

**Pitfall:** Putting the language instruction lower in the prompt (after lead context, brand voice, or channel guide) is less reliable. The model prioritizes instructions near the beginning. Place it as the first non-structural sentence of the system prompt, immediately after the role introduction.

**Verification:** After applying the fix, send a test message in the agent chat. The response must be in English regardless of lead data (Indian names, cities, industry references).

**If LLM is unavailable** → action stays pending (hard fail). No degraded fallback.

### Sequential Message Context (May 2026 — Implemented)

`_generate_step_message()` now receives conversation history and generates messages that feel sequential and human:

- **Msg 1:** Warm introduction with value prop
- **Msg 2:** "Just bringing this to the top of your inbox…" + refreshed value prop
- **Msg 3:** "I know things are busy, so I'll keep this brief…" + key benefit
- **Msg 4+:** Social proof / case study, fresh angle

**Implementation:**

1. In `_execute_action()`, before calling `_generate_step_message()`, query the last 5 outbound WhatsApp conversations:
```python
from database import Conversation as _Conv
recent_msgs = db.query(_Conv).filter(
    _Conv.lead_id == lead.id,
    _Conv.channel == "whatsapp",
    _Conv.direction == "outbound",
).order_by(_Conv.created_at.desc()).limit(5).all()
recent_msgs.reverse()
```
2. Build a `conv_summary` string: `"Previous messages in this sequence:\n 1. \"...\"\n 2. \"...\""`
3. Pass to `_generate_step_message(step, lead, config, step_index, total_steps, repeat_idx, total_repeats, conv_summary)`

4. In `_generate_step_message()`, the prompt now includes:
```
## Previous Messages in This Sequence
<conv_summary or "No prior messages — this is the first outreach.">

## Follow-up Style Guide
<auto-generated based on step position and whether history exists>
- First outreach: warm intro
- 2nd: "Just bringing this to the top of your inbox... + value prop"
- 3rd: "I know things are busy, so I will keep this brief... + key benefit"
- 4+: social proof / case study
- Never repeat phrasing from previous messages
- Vary opening, value prop angle, and CTA
```

**Signature:** `_generate_step_message(step, lead, config, step_index, total_steps, repeat_idx=0, total_repeats=1, conv_summary="")`

**Pitfall:** The Follow-up Style Guide is built as a variable (`style_guide`) before the f-string to avoid complex ternary-in-f-string syntax errors.

### Auto-Response Stage-Change Detection (May 2026 — Implemented)

**Problem:** When a lead says "let's meet at 2pm tomorrow" on WhatsApp, Ava's auto-response replies correctly but NEVER calls `mark_meeting_booked`. The lead stays at `engaged`, no meeting notification is created, no email summary is sent.

**Solution (background thread, not tool execution):** Instead of adding tool-parsing to the LLM response, use a post-send analysis function `_detect_stage_changes()` that runs in a background thread after Ava's auto-response is sent:

```python
def _detect_stage_changes(lead, inbound_msg, outbound_msg, tenant_id, db):
    """Analyze conversation for meeting bookings and qualification signals."""
    # Only check engaged/reached_out/new leads
    # Ask LLM: did the lead agree to meet? qualify?
    # Execute appropriate action (mark_meeting_booked, auto-qualify)
```

**Lightweight analysis prompt:**
```
{
  "meeting_booked": true/false,
  "meeting_details": "Only if meeting booked: time/day/details mentioned",
  "qualification": "positive" | "neutral" | "negative" | null,
  "action_needed": "none" | "meeting" | "qualification" | "follow_up"
}
```

**Actions when meeting is detected:**
1. Set `lead.stage = "meeting_booked"`
2. Cancel all pending ScheduledActions
3. Create ActionItem for human notification (type=meeting_request)
4. Call `_sync_deal_stage_from_lead(lead.id)`
5. **Send email summary + `.ics` calendar invite** via Gmail API (see Omnichannel section)

**Actions when qualification is detected (`qualification == "positive"`):**
1. Set `lead.stage = "qualified"`
2. Call `_sync_deal_stage_from_lead(lead.id)`

**Trigger point:** Called from `_ava_auto_respond()` alongside `analyze_conversation()`:

```python
import threading as _ta
_ta.Thread(target=analyze_conversation, args=(lead, conv, outbound, tenant_id, init_db()), daemon=True).start()
_ta.Thread(target=_detect_stage_changes, args=(lead, lead_message, response, tenant_id, init_db()), daemon=True).start()
```

**Why this approach (not tool execution in LLM output):**
- Doesn't require the LLM to output structured tool calls in response text
- Runs async — doesn't slow down the WhatsApp reply (lead sees response immediately)
- Clean separation: conversation response + analysis in parallel
- Same analysis prompt works for any channel (WhatsApp, email, call)

**This fixes three bugs at once:**
1. Lead stage doesn't move to `meeting_booked` → now auto-detected and set
2. No email summary sent → now sent via Gmail with .ics attachment
3. No dashboard notification → ActionItem created

See `references/ics-utils.md` for `.ics` generation API and time parsing details.

### Omnichannel Meeting Flow (May 2026 — Implemented)

When a meeting is booked (via `mark_meeting_booked` tool or auto-detected), the system now sends an email summary + `.ics` calendar invite:

**Flow:**
```
Lead: "2pm tomorrow works"
  → Ava: "2pm tomorrow works perfectly! Looking forward to it"
  → [background] _detect_stage_changes → meeting_booked
  → [background] Email sent via Gmail:
      Subject: "Meeting Confirmation - {lead.name}"
      Body: Summary of WhatsApp conversation + "A calendar invite is attached"
      Attachment: .ics file with parsed meeting time
```

**Implementation in `mark_meeting_booked` tool (line ~2448):**
1. Query Gmail tokens from `integration_config` table (`integration_id = "email-gmail"`)
2. Generate `.ics` file via `ics_utils.create_ics(lead.name, meeting_details)`
3. Send via `send_via_gmail_api(tokens, lead.email, subject, body, body_html, attachments=[(filename, ics_bytes)])`

**The `send_via_gmail_api` function was updated to support attachments:**
```python
def send_via_gmail_api(tokens, to, subject, body, body_html=None, attachments=None):
    # attachments: list of (filename, bytes) tuples
    # Builds MIMEMultipart("mixed") when attachments present
```

**`.ics` generation (`ics_utils.py`):**
- `create_ics(lead_name, meeting_details, duration_minutes=60, organizer="Ava from Hunar.ai")`
- Parses natural language meeting time from `meeting_details` ("2pm tomorrow", "Thursday 3pm")
- Falls back to next day 11am if time can't be parsed
- Includes 15-minute alarm

**Channel-aware follow-up (rule from Greg):**
- Summary should only be sent for **stage-changing conversations**, not every chat
- If conversation started on WhatsApp → send email summary + .ics
- If conversation started on email → send WhatsApp crisp summary instead
- The email is the authoritative summary channel; WhatsApp is for concise confirmation

### Cadence Debugging — Common Failure Modes

When cadence trigger fails but the user has clearly published a config, the issue is almost always on the **lead side**, not the template side.

**For a comprehensive failure mode table and step-by-step diagnostic procedures, see `references/cadence-debugging-failure-modes.md`.** This reference covers the complete matrix: transient backend errors, lead-side diagnostics (NULL cadence_type, wrong type), stale cancelled action cleanup, system prompt diagnostics, email signature verification, and full SQL commands for each check.

#### Debugging Protocol

Check BOTH sides in parallel:

```bash
# 1. Verify the template IS published in DB
cd /Users/greg/ara && sqlite3 ara.db "SELECT template_id, substr(config,1,120) FROM cadence_configs;"

# 2. Check if the lead actually has a cadence_type set
sqlite3 ara.db "SELECT id, name, company, stage, cadence_type, lead_source FROM leads WHERE id='LEAD_ID';"
```

**Root cause:** `trigger_cadence` calls `_schedule_cadence_for_lead()` which checks `lead.cadence_type`. If it's NULL, returns `"no cadence_type"`. This is different from "no config for {cadence_type}" (template not found in DB).

#### Most Common Cause: Pre-May 24 Leads

Leads created **before the `determine_cadence()` auto-assignment code was implemented** have NULL `cadence_type`. Creation endpoint (`create_lead` at line 425) sets `cadence_type` on creation, but existing leads never got backfilled.

**Fix (applied May 30, 2026):**
1. **Migration** in `lifespan()` — backfills NULL `cadence_type` using `determine_cadence(lead_source, stage)`:
   ```python
   null_cadence_leads = db_session.execute(
       sa_text("SELECT id, lead_source, stage FROM leads WHERE cadence_type IS NULL")
   ).fetchall()
   for lead_row in null_cadence_leads:
       lid, lsource, lstage = lead_row
       ct = determine_cadence(lsource or "form", lstage or "new")
       db_session.execute(
           sa_text("UPDATE leads SET cadence_type = :ct, cadence_auto_assigned = 'yes', cadence_updated_at = :now WHERE id = :lid"),
           {"ct": ct, "lid": lid, "now": utcnow()}
       )
   ```
2. **Resilience** in both `trigger_cadence_for_lead()` (API) and `execute_tool` handler for `trigger_cadence` (Ava) — auto-assign `cadence_type` if NULL before scheduling:
   ```python
   if not lead.cadence_type:
       lead.cadence_type = determine_cadence(lead.lead_source or "form", "reached_out")
       lead.cadence_auto_assigned = "yes"
       lead.cadence_updated_at = utcnow()
   ```

#### Cadence Type Mapping Rules

```python
CADENCE_MAPPING = [
    (lambda s, st: s in ('form','meta','google','referral') and st != 'dormant', 'inbound'),
    (lambda s, st: st in ('dormant','lost'), 'nurture'),
]
# Fallback (implicit, from determine_cadence returning 'cold' if no match):
# Anything else → 'cold'
```

So: form submissions → `inbound`, dormant/lost → `nurture`, everything else (including CSV imports) → `cold`.

#### Other Failure Modes

| `reason` from `_schedule_cadence_for_lead` | What it means | Fix |
|-----------|---------------|-----|
| `no cadence_type` | Lead has NULL `cadence_type` | Auto-assign via `determine_cadence()` |
| `no config for {type}` | Cadence template for that type was never published | Publish the cadence via UI or API |
| `no steps` | Template has no `steps` array (empty config) | Add steps and re-publish |
| `stage={stage}` | Lead is at engaged+ stage and gate blocks it | Reset stage to `reached_out` (done by trigger endpoint) |
| `{N} pending actions exist` | Lead already has pending actions | The trigger endpoint cancels old ones first, but the check runs again after — if new actions were just created, this is a false positive from double-trigger |

**Cascade collapse (not a returned `reason` — silent data bug):**
| Symptom | What it means | Fix |
|---------|---------------|-----|
| All N email repeats show the **same** `scheduled_at` in the DB | Each repeat was computed independently from `now` + working hours pushed all of them to the identical slot | Already fixed (May 30) — repeats now cascade from the previous adjusted time. Use `delay_hours=0` for immediate start |

#### Pitfall: Pre-May-24 leads with NULL cadence_type — Ava reports "not set up"**

When a user says "Ava says the cold cadence hasn't been set up" but the template IS published in the DB, the issue is on the **lead side**, not the template side. Check:

1. Does the lead have a `cadence_type`? (`sqlite3 ara.db "SELECT cadence_type FROM leads WHERE id='LEAD_ID';"`)
2. Is the template published? (`sqlite3 ara.db "SELECT template_id FROM cadence_configs;"`)
3. If lead has `cadence_type` but it differs from what the user asked for (e.g., lead is "inbound" but user asked for "cold"), update the lead's cadence_type: `curl -s -X PATCH 'http://localhost:8766/api/leads/LEAD_ID/cadence' -H 'Content-Type: application/json' -d '{"cadence_type": "cold"}'`

#### Verification

```bash
# After fix, verify by triggering cadence for the lead
curl -s -X POST "http://localhost:8766/api/cadence/trigger/lead/LEAD_ID" | python3 -m json.tool

# Expected: {"scheduled": N, "cadence_type": "cold|inbound|nurture", ...}
# If scheduled=0, check the "note" field for the reason
```

### Restart Outbound Stage Reset (May 2026 — Fixed)

`trigger_cadence_for_lead()` now resets `lead.stage = "reached_out"` before calling `_schedule_cadence_for_lead()`. This bypasses the engaged+ stage guard and lets the restart flow actually work:

```python
# In trigger_cadence_for_lead():
lead.stage = "reached_out"
lead.updated_at = utcnow()
db.commit()
result = _schedule_cadence_for_lead(lead, db)
```

**Without this reset,** Restart Outbound returns `{"scheduled": 0, "reason": "stage=engaged"}` silently — the button appears to fire but no actions are created.

### ⚠️ Critical Pitfall: `desc` + `fields` Coexistence

If a step has BOTH a `desc` (LLM instruction) AND `fields` (opening/value/cta), the code at `_schedule_cadence_for_lead()` line 1612 takes the **legacy path** (`if desc and not fields` is False when `fields` is truthy). The `fields` values are concatenated verbatim and stored as the message payload — the `desc` is completely ignored.

**Result:** The user sees their step desc like "Warm intro about yourself + problem statement hook..." being sent as the literal message text, instead of an LLM-generated message based on it.

**Fix:** Always remove `fields` from steps that have a `desc`. The `desc` already contains the right LLM instruction. Delete `fields` from the step config:
```json
// BEFORE (broken):
{
  "channel": "whatsapp",
  "desc": "Warm intro about yourself + problem statement hook...",
  "fields": {"opening": "Warm intro about yourself", "value": "Reducing TAT", "cta": "Let's chat"}
}

// AFTER (correct):
{
  "channel": "whatsapp",
  "desc": "Warm intro about yourself + problem statement hook..."
}
```

**Cadence builder UI:** The UI should not offer field-based inputs when a step has a `desc`. The two modes are mutually exclusive. When migrating old cadences, the `loadData()` conversion should strip `fields` if `desc` is present.

**DB remediation:** To fix existing cadence configs:
```sql
-- Check affected configs
SELECT id FROM cadence_configs WHERE json_extract(config, '$.steps') LIKE '%"desc"%' AND json_extract(config, '$.steps') LIKE '%"fields"%';

-- Fix via Python: load config, loop steps, delete fields if desc present, save back
```

### Auto-Response Send Result Check (May 2026 — Fixed)

When `_handle_inbound_whatsapp()` generates an Ava auto-response and sends it via `wa.send_message_sync()`, it checks the return value to decide whether to log the outbound conversation:

```python
send_result = wa.send_message_sync(phone_clean or phone, response)
if send_result.get("status") == "sent" or "msg_id" in send_result:
    # Log the outbound conversation
```

**Bug (fixed):** The original code checked `send_result.get("success")` which is NEVER a key in the Baileys sidecar client response. The sidecar returns `{"status": "sent", "msg_id": "..."}` on success and `{"error": "..."}` on failure. The `success` key does not exist, so the condition was always falsy. Result: Ava's auto-response was sent but never logged as a conversation, making it invisible to future queries.

## WhatsApp Send Fix (May 2026)

**Problem:** `_execute_action()` called `wa.send(phone, message)` on the WhatsApp manager, but the actual method is `wa.send_message_sync()`. This caused ALL WhatsApp scheduled actions to fail with `'WhatsAppManager' object has no attribute 'send'`.

**Fix:** Replace all 4 instances of `wa.send()` with `wa.send_message_sync()` in `_execute_action()` (server.py):

1. LLM-format WhatsApp path (line ~4336): `wa.send_message_sync(lead.phone, message_text)`
2. SMS path (line ~4373): `wa.send_message_sync(lead.phone, message_text)` — also calls `_handle_outbound_whatsapp()` to log the outbound
3. Fallback/else path (line ~4378): `wa.send_message_sync(lead.phone, message_text)`
4. Legacy format WhatsApp path (line ~4392): `wa.send_message_sync(lead.phone, message)`

**Verification:** After fix, check scheduler logs for successful WhatsApp sends instead of `'WhatsAppManager' object has no attribute 'send'` errors.

### Send Result Checking — CRITICAL (May 2026)

**Problem:** `wa.send_message_sync()` and `send_via_gmail_api()` both return error indicators (dict with `error` key, or `(bool, str)` tuple respectively), but `_execute_action()` **never checked the return values**. This meant:

- If WhatsApp was disconnected, `send_message_sync` returned `{"error": "WhatsApp not authenticated..."}`
- If Gmail tokens expired, `send_via_gmail_api` returned `(False, "error message")`
- But `_execute_action()` returned `True` regardless, and the scheduler marked the action as `completed`
- The user saw "completed" in the UI but never received the message

**Fix:** Check return values in all four code paths in `_execute_action()`:

```python
# WhatsApp (interpolated payload path)
result = wa.send_message_sync(lead.phone, message_text)
if isinstance(result, dict) and result.get("error"):
    action.last_error = result["error"]
    logger.warning(f"WhatsApp send failed for {lead.name}: {result['error']}")
    return False

# Email (interpolated payload path)
success, err_msg = send_via_gmail_api(tokens, lead.email, subject, body)
if not success:
    action.last_error = f"Email send failed: {err_msg}"
    logger.warning(f"Email send failed for {lead.name}: {err_msg}")
    return False

# Also fix the legacy format paths with the same pattern
```

**Verification:** When WhatsApp is disconnected, actions now show `failed` status with `last_error` set instead of `completed`.

### Conversation Logging Fix (May 2026)

**Problem:** The scheduler's `_execute_action()` called `_handle_outbound_whatsapp(lead.phone, message_text)` to log outbound WhatsApp conversations. But `_handle_outbound_whatsapp()` opens its own database session with `init_db()`. SQLite has a concurrency limit — if the scheduler's session holds a write lock, `_handle_outbound_whatsapp()`'s session gets a database locked error. The error was silently caught by a broad `except Exception` block, so no conversation was ever logged.

**Fix:** Don't call `_handle_outbound_whatsapp()`. Instead, create the Conversation object directly in the scheduler's existing `db` session:

```python
try:
    from database import Conversation
    outbound = Conversation(
        lead_id=lead.id,
        tenant_id=TENANT_ID,
        channel="whatsapp",
        direction="outbound",
        subject=f"Outbound cadence to {lead.name}",
        content=message_text,
        summary="",
        sentiment="",
    )
    db.add(outbound)
    if lead.stage == "new":
        lead.stage = "reached_out"
        lead.updated_at = utcnow()
    db.commit()
    logger.info(f"Outbound cadence WhatsApp logged for {lead.name}")
except Exception as e:
    logger.error(f"Failed to log outbound WhatsApp conversation: {e}")
```

**Key difference:** Uses the scheduler's own `db` session (passed as parameter to `_execute_action`), not a new session from `init_db()`. Avoids SQLite locking conflicts because there's only one writer.

**Future pattern:** Any time you need to make DB changes inside the scheduler loop, always use the passed-in `db` session. Never open a new session with `init_db()` inside `_execute_action()` or any function called from it.

### Pause/Resume Cadence Buttons (May 2026 — Refactored)

Both buttons **always visible** in the lead header next to Start AI Chat. No conditional show/hide.

**▶ Restart Outbound** (blue outline, `data-action="trigger-cadence"`)
- Calls `POST /api/cadence/trigger/lead/{id}` — cancels old pending + re-schedules fresh cadence
- Always clickable

**⏸ Pause Outbound** (red outline, `data-action="pause-cadence"`)
- Calls `POST /api/cadence/pause/lead/{id}` — cancels all pending/firing actions
- **Disabled + grayed out** when no pending actions exist (uses CSS class `.disabled` + HTML `disabled` attribute)

```javascript
var hasPending = l.scheduled_actions && l.scheduled_actions.length > 0;
// In lead header template:
'<button class="lead-btn primary-outline" data-action="trigger-cadence" ...>▶ Restart Outbound</button>' +
'<button class="lead-btn pause-btn' + (!hasPending ? ' disabled' : '') + '" data-action="pause-cadence" ...' + (!hasPending ? ' disabled' : '') + '>⏸ Pause Outbound</button>'
```

**Backend endpoint:** `POST /api/cadence/pause/lead/{lead_id}` — cancels all pending/firing ScheduledActions for the lead.

```python
@app.post("/api/cadence/pause/lead/{lead_id}")
def pause_cadence_for_lead(lead_id: str):
    pending = db.query(ScheduledAction).filter(
        ScheduledAction.lead_id == lead.id,
        ScheduledAction.tenant_id == TENANT_ID,
        ScheduledAction.status.in_(["pending", "firing"]),
    ).all()
    for pa in pending:
        pa.status = "cancelled"
        pa.updated_at = utcnow()
    db.commit()
    return {"lead": lead.name, "cancelled": cancelled, "status": "paused"}
```

**Confirmation dialogs** (`confirm()` before action):
- **Restart:** `'Are you sure? This will restart the outbound campaign for this lead — it will cancel all existing pending activities (emails, WhatsApp, calls) and reschedule the full sequence from scratch.'`
- **Pause:** `'Are you sure? This will pause the outbound campaign for this lead — all pending activities (emails, WhatsApp, calls) will be cancelled. You can use "Restart Outbound" to resume later.'`

Both actions call `showLeadDetail(leadId)` on completion to refresh the lead detail with the new button state and scheduled actions in the Outreach tab.

**CSS:**
```css
.lead-btn.pause-btn { border-color: #dc2626; color: #dc2626; }
.lead-btn.pause-btn:hover { background: #fee2e2; }
.lead-btn.pause-btn.disabled { opacity: .4; cursor: not-allowed; border-color: #d1d5db; color: #9ca3af; }
.lead-btn.pause-btn.disabled:hover { background: transparent; }
.lead-btn.primary-outline { border-color: #2563eb; color: #2563eb; }
.lead-btn.primary-outline:hover { background: #dbeafe; }
```

**Event delegation handles:**
```javascript
if (action === 'trigger-cadence') { triggerLeadCadence(t.dataset.leadId); return; }
if (action === 'pause-cadence') { pauseLeadCadence(t.dataset.leadId); return; }
```

**History:** Originally the buttons toggled (Pause when pending, Schedule when not). Greg requested both always visible. The Schedule button was renamed to Restart Outbound, and Pause to Pause Outbound for parallel naming. Old confirmation dialogs were added later.

**Determination logic:**
```javascript
var hasPending = l.scheduled_actions && l.scheduled_actions.length > 0;
```

**Key UX decisions:**
- The old `▶ Schedule` button was renamed to `▶ Restart Outbound` on Greg's request (clearer intent)
- `⏸ Pause` was renamed to `⏸ Pause Outbound` (parallel naming with Restart)
- Both buttons ALWAYS visible — no toggling between them
- Pause button is disabled (grayed + non-interactive) when no pending actions exist
- Confirmation dialogs prevent accidental triggers
- The old in-cadence-row Schedule button was removed — all cadence actions live in the lead header

### Working Hours Constraint (IST Timezone)

The cold cadence template conditions control when email/call steps fire. WhatsApp is NOT subject to any working hours or day-of-week constraints — it fires at `delay_hours` immediately regardless.

**Condition fields:**
| Field | Type | Effect |
|-------|------|--------|
| `workingHours` | bool | Constrain email/call to 9AM-6PM IST |
| `weekdays` | bool | Block weekends by default (fallback when saturday/sunday not set) |
| `saturday` | bool | Explicitly allow (true) or block (false) Saturday. Overrides `weekdays` |
| `sunday` | bool | Explicitly allow (true) or block (false) Sunday. Overrides `weekdays` |

**Resolution order in `_next_working_time()`:**
1. If `saturday`/`sunday` is explicitly set: use that value (true=allowed, false=blocked)
2. If they're NOT set: fall back to `weekdays` (true=block weekends, false/absent=allow all)

This means the old code that only checked `conditions.get("weekdays") and dt_ist.weekday() >= 5` was wrong — it blocked ALL weekends regardless of `saturday`/`sunday` fields. The inbound template had `saturday: true` but the old function still blocked Saturdays.

**Working hours logic (when `workingHours: true`):**
- `dt.hour < 9 IST` → snap forward to 9:00 AM same day
- `dt.hour >= 18 IST` → advance to next day 9:00 AM, then check if that day is a blocked weekend day
- Between 9-18 IST → no adjustment, fire as scheduled

**Timezone fix (May 2026):** `_next_working_time()` originally checked `dt.hour` in UTC, pushing Indian emails to 09:00 UTC (2:30PM IST). Fixed by converting to IST (UTC+5:30) before checking, converting back to naive UTC for storage.

**Key details:**
- All datetime arithmetic happens in IST
- Weekday check uses `dt_ist.weekday()` — Monday=0, Saturday=5, Sunday=6
- Result converted back to naive UTC for SQLite storage
- Always guard `astimezone` with `if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)`

**Pitfall:** Forgetting the naive datetime guard before `astimezone` raises `TypeError`. Check `tzinfo is None` first.

### Scheduler-Recommended DB Patterns

When working in the scheduler loop (`_execute_action`, `_schedule_cadence_for_lead`, `_check_dormant`, etc.):

1. **Use the passed-in `db` session.** Never call `init_db()` to open a new session inside these functions — SQLite's locking model causes `database is locked` errors with concurrent sessions.
2. **Always check send results.** `wa.send_message_sync()` and `send_via_gmail_api()` return error indicators that must be checked. Ignoring them leads to false "completed" status.
3. **Set `action.last_error` before returning `False`** from `_execute_action()`. The scheduler uses this error message for logging and retry decisions.
4. **Commit after changes.** `db.commit()` must be called after any `db.add()` or attribute mutation on ORM objects, or changes are lost when the session is closed.
5. **Never re-import module-level names inside function bodies.** If a name is already imported at module level (e.g. `from database import Conversation` at the top of `server.py`), do NOT repeat the import inside any handler or tool function. Python treats the name as a LOCAL variable for the entire function, but the import only executes if that specific code path runs. Code paths that access the name before the import executes raise `UnboundLocalError`. This bug is silent at module load time — only surfaces at runtime when the execution order is non-deterministic (different endpoints called first). **Example from May 30:** `from database import Conversation` inside `get_summary()` handler crashed `get_lead_detail()` — `Conversation` was read by `get_lead_detail()` before `get_summary()` ever executed. **Fix:** Always use the module-level import. If a name is truly only needed in one function, use `import module; module.Name()` syntax or move the import to the top of the file.

### Scheduled_at Timestamp Timezone (May 2026)

ScheduledAction timestamps are stored as naive UTC datetimes in SQLite. When returned via the API, they MUST include the `Z` suffix to mark them as UTC, otherwise `new Date()` in JavaScript interprets them as browser-local time (or fails to parse):

```python
# In API responses:
"scheduled_at": a.scheduled_at.isoformat() + "Z" if a.scheduled_at else None,
```

Without the `Z` suffix, JavaScript adds 5:30 hours (IST) on top of the UTC time, showing times 5:30h off from reality.

### Cache-Bust Pattern for Frontend Changes

Every time dashboard.js is modified, bump the version in `dashboard_template.py`:

```html
<script src="/static/dashboard.js?v=N"></script>
```

Increment N by 1 each time. This forces the browser to fetch the latest JS instead of serving a stale cached copy. No cache-bust = hard refresh required or user sees old behavior.

### Preview

`/api/cadence/preview` accepts `systemPrompt`, `stepDesc`, `stepIndex`, `totalSteps`, `repeatIdx`, `totalRepeats` and uses the same prompt assembly logic.

### Backward Compat

Old-format steps (with `day`/`delay`/`fields`) use the interpolation path. `loadData()` in `cadence_template.py` converts old data on load.

### System Prompt Persistence — Common Pitfall

Two bugs caused the system prompt to disappear on page refresh:

1. **Migration bug:** `if (!data[key].systemPrompt)` treats `""` as falsy → overwrites with default. **Fix:** `if (data[key].systemPrompt === undefined)` — undefined only.
2. **No real-time persistence:** system prompt textarea had no `change` handler. **Fix:** add `change` event → `t.systemPrompt = e.target.value; saveData()`.

**Rule:** Every editable field must persist to localStorage on `change` (blur), not only on Publish.

### Unsaved Changes Warning

`beforeunload` listener checks `hasUnsavedChanges`. All input events set the flag; `saveCurrentState()` clears it. Covers refresh, tab close, back/forward, and sidebar nav.

### Cadence Builder UI Evolution

| Version | Change |
|---------|--------|
| v1 | Old field-based model (opening/value/cta per step) |
| v2 | System prompt + channel prompts (template-level) + step descs |
| v3 | Channel prompts moved per-step |
| v4 | Channel prompts merged into desc, SMS removed, Primary Goal box removed |
| v5 | Step desc textarea removed from UI — descs sourced from channel prompts only. Only timing controls remain editable per step |
| v6 | "Add Step" → "Add Channel". Dynamic channel picker shows only unused channels. SMS renamed to "Text". 4 channels available: WhatsApp, Email, Call, Text |

**Current layout (v5):** No textarea per step — descs sourced from channel prompts. Grey "channel prompt" label beside the step name. Timing controls (delay, repeat, interval) are the only editable fields. Objective goes as the first line of the system prompt.

### Ava's Prompt Generation (Planned — Phase 3)

To be built:
- At induction completion, Ava generates `systemPrompt` for all 3 cadences
- On significant skill promotion, Ava regenerates system prompts (flagging Greg's edits)
- Tool: `regenerate_cadence_prompts(template_id)` for on-demand regeneration

### 12. Conversational Playbook (May 2026 — Built)

The Conversational Playbook is the **post-engagement control surface** — what Ava does after a lead replies and outbound sequences stop. Accessed from Outreach Central via tile below the Outreach Template bar.

#### Stage Model (5 Fixed Stages)

```
Engaged → Meeting Requested → Scheduled → Completed → Closed
```

- **Engaged** — Lead replied. Sequences stop. Ava replies contextually, detects intent disposition.
- **Meeting Requested** — Lead asked for a meeting/demo. Send calendar invite + confirmation + deck.
- **Scheduled** — Meeting on calendar. Send pre-reads + reminders.
- **Completed** — Meeting done. Send summary + next steps + stakeholder ask.
- **Closed** — Deal outcome. Archive, closeout per outcome, store notes for reactivation.

#### Per-Stage Configuration Sections

Two-column modal (left = workspace, right = live preview):

1. **Always active** (locked, Engaged only) — Reply on same channel, stop sequences, classify intent
2. **Intent Disposition** (Engaged only) — Chips: Interested, Not Interested, Busy, Considering, Meeting Intent, Gatekeeper. Toggleable, addable, auto-detected by Ava.
3. **Actions on entry** — Orderable rows with toggle, description. Different defaults per stage.
4. **Follow-up rules** — If/then/timing dropdowns (no reply → send follow-up, negative sentiment → escalate)
5. **Escalation rules** — Trigger + severity (negative_sentiment, pricing_negotiation, compliance_question, human_requested)
6. **Communication style** — Tone (consultative|direct|warm|formal), Length (short|clear|detailed), Boundaries (no pricing/pricing allowed/escalate pricing)
7. **Attachments & case studies** — Asset shelf with type badges + pin-to-primary + browse KB button

#### Data Model (in cadence config `playbook` key)

```json
{
  "playbook": {
    "engaged": {
      "intents": ["Interested","Not Interested","Busy","Considering","Meeting Intent","Gatekeeper"],
      "activeIntents": ["Interested","Considering","Meeting Intent"],
      "actions": [{"name": "Summarize conversation", "icon": "", "enabled": true}],
      "rules": [{"if": "no_reply", "time": 24, "then": "send_followup"}],
      "escalations": [{"trigger": "negative_sentiment", "severity": "medium"}],
      "style": {"tone": "consultative", "length": "clear", "boundaries": "no_pricing"},
      "assets": [{"name": "Company Deck", "type": "PDF", "pinned": true}]
    },
    "meeting": { "actions": [...], "rules": [...], ... },
    "scheduled": { "actions": [...], "rules": [...], ... },
    "completed": { "actions": [...], "rules": [...], ... },
    "closed": { "actions": [...], "rules": [...], ... }
  }
}
```

#### UI Conventions
- Large centered modal with fade/scale animation (`.playbook-overlay`, `.playbook-modal`)
- Stage rail across top with arrows (`.playbook-rail-stage.active` changes background #111)
- Right column live preview updates on toggle/switch
- Monochrome palette (#FFFFFF, #F5F5F7, #E5E5E7, #6E6E73, #111111)
- Rounded cards (`.pb-section`), soft borders, toggle switches (`.pb-action-toggle.on`)
- Intent chips active=black/#111, inactive=gray/#F5F5F7
- Drag handles (⠿) on action rows, lock icons on always-active rows
- JS functions: `openPlaybook()`, `closePlaybook()`, `switchPlaybookStage()`, `renderPlaybookStage()`, `renderPlaybookPreview()`, `toggleIntent()`, `toggleAction()`, `getDefaultStageConfig()`

#### Key Files
- `cadence_template.py` — All HTML/CSS/JS inline
- `getDefaultStageConfig(stage)` — Opinionated defaults per stage with different actions, rules, assets, and communication styles
- Data persists to localStorage via `saveData()`/`getTemplate()` pattern

#### Playbook UI Quirks & Fixes

**1. Toast hidden behind overlay**
- **Symptom:** Clicking "+ Add Action" or "+ Add Rule" appears to do nothing.
- **Root cause:** The toast element (`#toast`) has `z-index: 100` but the playbook overlay has `z-index: 10000`. The toast renders behind the overlay — invisible to the user. The buttons DO fire `showToast('Add action — coming soon')`, the message just can't be seen.
- **Fix:** Set `#toast` z-index to `10001` (one above the overlay's 10000). Located in the CSS block in `cadence_template.py`.
- **Applies to:** Both "+ Add Action" and "+ Add Rule" buttons — both use `showToast()` for their placeholder messages.

**2. "Actions on entry" description — static "this stage"**
- **Symptom:** The Actions on entry section always says "What Ava does when a lead enters this stage" regardless of which playbook stage (Engaged, Meeting Requested, etc.) is selected.
- **Fix:** Use the stage label variable that's already in scope:
  ```python
  html += '<div class="pb-section-desc">What Ava does when a lead enters the ' + (label.name || stage) + ' stage</div>';
  ```
  `label.name` is set from `stageLabels[stage].name` earlier in `renderPlaybookStage()` — it says "Engaged", "Meeting Requested", etc.

**3. OOO/auto-reply detection missing from "Always active"**
- **Symptom:** Engaged stage "Always active" section only listed 3 behaviors (Reply on same channel, Stop outbound sequences, Classify intent disposition). Auto-replies and out-of-office messages would be classified as engagement.
- **Fix:** Added a 4th locked row:
  ```python
  html += '<div class="pb-locked-row"><span class="pb-lock-label">Auto-detect auto-replies & OOO</span><span class="pb-lock-sub">Out-of-office, auto-reply mailers, and bot responses are detected and ignored — not classified as engagement</span></div>';
  ```

**4. Validate endpoint token metric pitfall (server.py)**
- When calculating `modules.security` token count, `len(prompt_parts.get("security", ""))` will return the **number of dict keys** (4 keys → 4 // 4 = 1 tok) because `collectPbParts()` returns security as a dict. Must use `json.dumps()` to serialize to string first, same as `brand`, `sector`, and `channels`. See `security-token-count-bug` skill for details.

#### Stage Defaults Summary

| Stage | Actions | Escalations | Style |
|-------|---------|-------------|-------|
| Engaged | Summarize, Notify owner, Case study (opt) | Negative sentiment, Pricing, Compliance | Consultative, No pricing |
| Meeting Req | Calendar invite, WhatsApp confirmation, Attach deck, Notify | Reschedule | Warm, Pricing allowed |
| Scheduled | Pre-read (1h before), Reminder (15min) | Cancellation | Warm, Short |
| Completed | Summary, Next steps, Stakeholder ask (opt) | None | Warm, Clear |
| Closed | Archive, Closeout (won), Closeout (lost), Storage | None | Warm, Short |

#### Playbook Save Persistence — Quick-Verify Pattern

When the user reports "save didn't stick" (rules revert after close/reopen), use the browser console to verify the full save round-trip without touching the UI:

```javascript
// Step 1: Check current rules
var rules = getPlaybookData().engaged.rules;
console.log('BEFORE:', JSON.stringify(rules));

// Step 2: Modify and persist
getRules()[0].time = 48;  // change a value
savePlaybook();            // save to localStorage

// Step 3: Verify in localStorage directly
var saved = JSON.parse(localStorage.getItem('ara_cadence_data'));
console.log('LOCALSTORAGE:', saved.cold.playbook.engaged.rules[0].time);
// Expected: 48

// Step 4: Close and reopen (in-memory)
closePlaybook();
openPlaybook();
console.log('AFTER REOPEN:', JSON.stringify(getPlaybookData().engaged.rules[0].time));
// Expected: 48 — if this fails, the save function isn't persisting to the template object

// Step 5: Page refresh test (if step 4 passed, step 5 tests full persistence)
// location.reload() — then check localStorage again
```

**Common failure modes and what they mean:**

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| `localStorage` has old data but you called `savePlaybook()` | JS function doesn't exist (syntax error in script) | Check `typeof savePlaybook` → page reload |
| `localStorage` has new data but reopen shows old | `openPlaybook()` creates fresh `playbookData = null` and reads `t.playbook` from `TEMPLATES` — but `t.playbook` is stale because `savePlaybookData()` didn't set it | Check `savePlaybookData()` sets `t.playbook = playbookData` correctly |
| localStorage has new data, reopen shows new but page refresh loses it | `DEFAULT_TEMPLATES` lacks a `playbook` field → `loadData()` merge creates empty entries | Add `playbook: {}` to `DEFAULT_TEMPLATES[cold]` |
| Functions exist, save works, but `openPlaybook()` shows defaults | `getPlaybookData()` does `t.playbook = {}` when `playbook` is undefined on the template — `savePlaybookData()` never set it because it was called when data was fresh | After any `savePlaybookData()` call, verify it actually updated `t.playbook` |
| **Dropdowns save but text inputs don't** | `onchange` on `<input type="text">` fires on **blur**, not on value change. Clicking "Save Changes" button may trigger `savePlaybook()` before the blur/change sequence completes. The text value sits in `input.value` but never reaches the data model. | Fix `savePlaybook()` to **read text input values directly from the DOM** before saving (see below) |

**Step-by-step for the "save didn't stick" report:**

1. Open the playbook, make a change, click Save Changes
2. **Without closing**: `JSON.parse(localStorage.getItem('ara_cadence_data')).cold.playbook.engaged.rules[0]` — check the value updated
3. Close and reopen: `JSON.stringify(getPlaybookData().engaged.rules[0])` — should still have your change
4. If step 2 works but step 3 fails → `openPlaybook()` is reading stale data despite localStorage being correct (memory sync bug)
5. If step 2 fails → the save function never fired; check `typeof savePlaybook` and function existence in the script

#### ⚠️ Critical: Text Input Save Race Condition

**Symptom:** Adding a rule or changing a text field (the "then" NLP input) doesn't persist after Save, though dropdown changes (if/time) save fine. The rule row appears but the typed text reverts to the default.

**Root cause:** The text input uses `onchange="updatePlaybookRule(this)"`. For `<input type="text">`, the `change` event fires **only when the element loses focus** (blur), not on value change. When the user types in the text box then clicks "Save Changes":

1. User clicks button → browser processes `mousedown`
2. Text input loses focus → blur fires → **`change` fires on text input** → `updatePlaybookRule(this)` updates data model
3. Then `mouseup` → `click` on button → `savePlaybook()` serializes data model

**But there's a race:** If the blur/change sequence doesn't complete before the click handler fires (depends on browser event processing), `savePlaybook()` serializes the data model **without the text input's value**. The dropdowns work because `<select>` fires `change` immediately on option selection — no blur dependency.

**Fix (in `cadence_template.py`):** Override `savePlaybook()` to read all rule input values directly from the DOM before saving, rather than relying on the data model having been updated by event handlers:

```javascript
function savePlaybook() {
  // Sync all text inputs to the data model (onchange may not have fired yet)
  var inputs = document.querySelectorAll('#playbookWorkspace input[data-field="then"]');
  inputs.forEach(function(inp) {
    var idx = parseInt(inp.dataset.ridx);
    var rules = getRules();
    if (rules[idx]) rules[idx].then = inp.value;
  });
  // Also sync selects for safety
  var selects = document.querySelectorAll('#playbookWorkspace select[data-field="if"], #playbookWorkspace select[data-field="time"]');
  selects.forEach(function(sel) {
    var idx = parseInt(sel.dataset.ridx);
    var field = sel.dataset.field;
    var rules = getRules();
    if (!rules[idx]) return;
    if (field === 'if') rules[idx]['if'] = sel.value;
    else if (field === 'time') rules[idx].time = parseInt(sel.value);
  });
  savePlaybookData();
  showToast('Playbook saved');
}
```

**Principle:** Any save function for template-rendered form inputs should read DOM values at save time. Never assume `onchange`/`oninput` event handlers have already updated the data model — especially for text inputs where `change` requires blur.

#### ⚠️ Common JS Bug: Undeclared Variable ReferenceError

**Symptom:** JavaScript on the cadence page throws `ReferenceError: doLoadTemplate is not defined` on every page load. Error is silently caught by the runtime but can corrupt subsequent execution.

**Root cause:** At the template load hook (`cadence_template.py:~2128`):
```javascript
var _origLoad = doLoadTemplate;   // ← doLoadTemplate was NEVER declared anywhere
doLoadTemplate = function(id) { ... };
```

`doLoadTemplate` is read but never declared with `var`/`function`. In non-strict mode this throws a `ReferenceError`. The error doesn't stop the entire `<script>` block (it's handled differently across browsers) but it corrupts the execution context and can cause downstream functions to fail silently.

**Fix:** Initialize `doLoadTemplate` as a local variable before reading it:
```javascript
var doLoadTemplate = window.doLoadTemplate || function(){};
var _origLoad = doLoadTemplate;
doLoadTemplate = function(id) { ... };
```

**Hunting pattern:** When investigating a "save doesn't work" bug, always check the browser console with a global error catcher:
```javascript
window.onerror = function(m, f, l, c, err) { console.log('GLOBAL_ERR:', m, f, l, c); };
```
Hidden ReferenceErrors in initialization code are a primary cause of otherwise-inexplicable save failures. These errors happen on page load — long before the user interacts with the save button — so they're easy to miss with a casual console check.

### 13. Playbook Overview Chips (May 2026)

The Outreach Template tile shows 7 overview chips: Brand, Sector, Security, WhatsApp, Email, Call. (Sequence was removed May 30, 2026 — it duplicated the cadence steps area and belonged there, not in the preview bar.)

Each chip gets CSS class `.pv-filled` when its corresponding prompt part is filled: chips check fields in `globalPromptParts` (brand, sector, security, whatsapp, email, call). Background goes from #F5F5F7 to #111 when filled. Auto-fills from induction on template load via `prefillFromInduction()`. No emoji icons in chip labels — plain text only per monochrome convention.

### 14. Custom Actions with Inline Editing & @-Mention Support (May 2026 — Built)

The **"+ Add Action"** button in the Actions on Entry section was made functional this session. Previously it was a placeholder that only showed a toast.

#### Flow
1. Click **"+ Add Action"** → `addAction()` prompts for the action name via `prompt()`
2. A new action row appears with the name and an empty **inline textarea** for the description
3. User types the description directly — **auto-saves on every keystroke** via `oninput="updateActionDesc(this)"`
4. ✎ button now only edits the name (description is always editable inline)
5. ✕ button removes with confirmation (`confirm()`)

#### Inline Textarea Rendering

The action description is rendered as a `<textarea>` (not a static `<span>`) so it's always editable. It uses `data-idx` for model binding:

```python
html += '<textarea class="pb-action-desc" data-idx="' + i + '" placeholder="Describe..." oninput="updateActionDesc(this)">' + 
    (a.desc || '').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</textarea>'
```

```javascript
function updateActionDesc(el) {
  var idx = parseInt(el.dataset.idx);
  var pd = getPlaybookData();
  if (!pd[activePlaybookStage]) return;
  var cfg = pd[activePlaybookStage];
  if (cfg.actions && cfg.actions[idx]) {
    cfg.actions[idx].desc = el.value;
  }
}
```

**Principle:** The description saves on every keystroke — no separate "Save" required. The Save button in the playbook overlay persists everything to localStorage.

#### JS Functions

```javascript
function addAction() {
  var name = prompt('Action name (e.g. "Send pre-read at 9AM"):');
  if (!name || !name.trim()) return;
  var pd = getPlaybookData();
  if (!pd[activePlaybookStage]) pd[activePlaybookStage] = getDefaultStageConfig(activePlaybookStage);
  var cfg = pd[activePlaybookStage];
  if (!cfg.actions) cfg.actions = getDefaultActions(activePlaybookStage).slice();
  cfg.actions.push({ name: name.trim(), icon: '', desc: '', enabled: true });
  renderPlaybookStage(activePlaybookStage);
  renderPlaybookPreview(activePlaybookStage);
  showToast('Action added: ' + name.trim());
}

function editAction(idx) {
  // Prompt for new name only — desc is inline editable
  var pd = getPlaybookData();
  ...
  a.name = newName.trim() || a.name;
  renderPlaybookStage(activePlaybookStage);
  renderPlaybookPreview(activePlaybookStage);
  showToast('Action updated');
}

function removeAction(idx) {
  if (!confirm('Remove this action?')) return;
  cfg.actions.splice(idx, 1);
  renderPlaybookStage(activePlaybookStage);
  renderPlaybookPreview(activePlaybookStage);
  showToast('Action removed');
}
```

#### @-Mention Integration in Action Descriptions

The description textarea has full @-mention autocomplete support (same system as the Prompt Builder). Users type `@` and get a dropdown of documents and contacts to reference.

**How it's wired:**

```javascript
// @-mention listener for playbook description textareas (cadence_template.py init)
document.addEventListener('input', function(e) {
  var ta = e.target.closest('#playbookWorkspace .pb-action-desc');
  if (!ta) return;
  // ... same @-detection logic as prompt builder ...
  if (atPos >= 0 && atPos < pos) {
    if (typeof createMentionDropdown === 'function') {
      createMentionDropdown();
      showMentionDropdown(ta, searchTerm);
    }
    return;
  }
  if (typeof closeMentionDropdown === 'function') closeMentionDropdown();
});
```

**Key:** The @-mention functions (`createMentionDropdown`, `showMentionDropdown`, `insertMention`, `closeMentionDropdown`) are **global** (declared in `prompt_builder_template.py` at the top level, not inside a closure), so they're accessible from any script on the page. The playbook listener simply calls them directly.

**Existing `click` listener** for `.mention-item` (in `prompt_builder_template.py`) is document-wide — it handles mention selections from the playbook dropdown automatically.

**User expectation:** `@` in the description textarea should feel native — the dropdown appears, the user selects an asset, `@AssetName` is inserted. No separate asset picker, no comma-separated list prompt.

#### Main Page Playbook Summary (`renderMainPagePlaybook()`)

After closing the playbook overlay, the main Outreach Central page updates the CONVERSATIONAL PLAYBOOK tile with a per-stage summary showing configured counts:

```
Engaged — 2 actions, 2 rules, 3 escalations
Meeting Requested — 4 actions, 1 rule, 1 escalation
Scheduled — 3 actions, 1 rule, 1 escalation
```

**Wiring:**
- Called from `closePlaybook()` — updates summary on every close
- Called from page init (`renderMainPagePlaybook()` after `loadData()`) — shows persisted data on first load
- Renders into `<div class="playbook-summary" id="playbookSummary">` div after the stage pills

```javascript
function renderMainPagePlaybook() {
  var container = document.getElementById('playbookSummary');
  if (!container) return;
  var t = getTemplate();
  if (!t || !t.playbook) { container.innerHTML = ''; return; }
  var pd = t.playbook;
  var stages = ['engaged','meeting','scheduled','completed','closed'];
  var labels = { engaged:'Engaged', meeting:'Meeting Requested', ... };
  var html = '';
  stages.forEach(function(s) {
    var cfg = pd[s];
    if (!cfg) return;
    var ruleCount = (cfg.rules || []).length;
    var escalationCount = (cfg.escalations || []).length;
    var actionCount = (cfg.actions || []).filter(function(a){return a.enabled !== false;}).length;
    if (ruleCount === 0 && escalationCount === 0 && actionCount === 0) return;
    html += '<div class="ps-row"><span class="ps-stage">' + (labels[s] || s) + 
      '</span> <span class="ps-rules">' + actionCount + ' action' + ... + '</span></div>';
  });
  if (!html) html = '<div style="font-size:11px;color:#D2D2D5;padding:4px 0;">No stages configured yet</div>';
  container.innerHTML = html;
}
```

**CSS:**
```css
.playbook-summary { padding:0 12px 8px; display:flex;flex-direction:column;gap:4px; }
.playbook-summary .ps-row { font-size:11px;color:#6E6E73;padding:3px 0;border-bottom:1px solid #f0f0f0; }
.playbook-summary .ps-stage { font-weight:500;color:#111; }
.playbook-summary .ps-rules { color:#6E6E73;margin-left:4px; }
```

### 15. Global Prompt Parts Architecture (May 2026 — Implemented)

The Outreach Template prompt parts are now **global** — shared across all three cadences (cold, inbound, nurture). Only the **objective** differs per template.

#### Data Separation

```javascript
// Global (shared by all cadences)
var globalPromptParts = {
  brandPersonality: { tone: 'warm', style: 'direct', ... },
  sectorSpecific: { valueProps: '...', caseStudies: '...', ... },
  security: '...',
  channelSpecific: { whatsapp: '...', email: '...', call: '...' }
};

// Per-template (each cadence has its own)
TEMPLATES.cold.objective = 'Book introductory discovery call...';
TEMPLATES.inbound.objective = 'Qualify and route inbound leads...';
TEMPLATES.nurture.objective = 'Nurture dormant accounts...';
```

#### System Prompt Assembly

`assembleSystemPrompt(t)` merges global parts + per-template objective:

```
## Objective
{t.objective}

## Brand Voice
Tone: warm | Style: direct | Vocabulary: strategic | Language: english
Communication Style: {bp.phrases}
Personality: {bp.personality}

## Sector Context
{globalPromptParts.sectorSpecific.valueProps}

## Security & Guardrails
{globalPromptParts.security}

## WhatsApp
{globalPromptParts.channelSpecific.whatsapp}
```

#### Migration

`migrateToGlobalPromptParts()` runs on page load: copies non-objective fields from any existing `t.promptParts` into `globalPromptParts`, strips them from all templates.

#### Per-template Objective Tile

The Outreach Central page has an **Objective** tile below the template cards and above the cadence section. It shows the current template's name + objective text. Clicking ✎ Edit (or clicking the text itself) calls `startObjectiveEdit()` which makes the preview div `contenteditable=true` and selects all text for immediate replacement. The user types directly inline — no pop-up. Pressing **Enter** (without Shift) or clicking elsewhere (`blur`) saves and exits edit mode (contenteditable=false, border removed). On blur, if the text changed, it updates `t.objective`, calls `saveData()`, `updateObjectivePreview()`, and `assembleSystemPrompt(t)`.

### Inline Objective Editing Pattern

The objective text uses a `contenteditable` div (not a textarea, not a pop-up):

```html
<div class="prompt-overview" id="objectivePreviewText"
     contenteditable="false"
     onfocus="onObjectiveFocus()"
     onblur="onObjectiveBlur()"
     onkeydown="onObjectiveKeydown(event)">
  Click to set the objective for this cadence
</div>
```

**JS functions** (in `cadence_template.py`):
- `startObjectiveEdit()` — Sets `contentEditable=true`, focuses, selects all text
- `onObjectiveFocus()` — Adds a `1px solid #111` border for visual editing state
- `onObjectiveBlur()` — Sets `contentEditable=false`, removes border, saves if text changed
- `onObjectiveKeydown(e)` — Enter (no Shift) prevents default and blurs (saves)

**Key behaviors:**
- **Edit button** and **text div** both trigger `startObjectiveEdit()`
- **Enter** (no Shift) saves and exits — no form submission needed
- **Shift+Enter** inserts a line break within the contenteditable
- **Click away** (blur) also saves — no separate "Save" button
- **Visual indicator:** on focus, a `#111` border appears; on blur, border goes to `none`
- **No `prompt()` pop-up** — this was the old behavior (removed June 2026)

This pattern is lightweight and works because the objective is short text (one line). For multi-field editing, use the Prompt Builder modal instead.

**Pitfall:** `contentEditable` divs don't natively support placeholder text. The "Click to set..." text is set via `el.textContent` in `updateObjectivePreview()` when `t.objective` is falsy — it's not a real HTML placeholder attribute.

Layout (current, May 2026):
```
LEAD→CADENCE MAPPING
OUTREACH TEMPLATE (global)              ← global tiles at top
CONVERSATIONAL PLAYBOOK (global)        ← global tiles at top
[Outbound] [Inbound] [Nurture]          ← template cards (per-template selection)
OBJECTIVE (per-template)                ← per-template objective below cards
OUTREACH CADENCE + CONDITIONS           ← steps + preview + conditions
```

#### Prompt Builder Changes

- Builder has 7 tabs (no Objective tab). Opens on Brand tab by default.
- Architecture bar renumbered: Brand=1, Sector=2, Security=3, WhatsApp=4, Email=5, Call=6, Final=F
- `savePromptAndClose()` saves `parts` to `globalPromptParts`, calls `/api/cadence/publish-global` to fan out to all three templates
- `validateAndCompile()` sends `{template_id: 'global', promptParts}` — objective is NOT sent to the global validate endpoint since it's per-template. It's appended separately at runtime via `assembleSystemPrompt()`.
- The aggregated prompt in the Builder shows only the global prompt parts (brand, sector, security, channels).

Path B = no LLM on open. Deterministic, instant, always consistent.

**Architecture:** Skills table → prefill templates (`prefill_generator.py`) → structured JSON → form fields.

**Skills sources:** induction docs, conversation learnings (daily cron), coaching capture (instant chat feedback), all landing in same `skills` table.

**Cadence-specific personae:** Cold = witty/consultative, Inbound = direct/qualifying, Nurture = patient/educational.

**Security section** includes injection guardrails, restricted claims, escalation rules, and FAQs — reads from skills table.

### Design Boundary: Prompt Builder vs Cadence Conditions

**Prompt builder manages content** (what Ava says). **Cadence template conditions manage behavior** (when Ava sends).

Working hours, weekdays, and day-of-week constraints belong in `t.conditions` inside `cadence_template.py` — **not** in the prompt builder's Security tab. The runtime reads from `template.get("conditions", {})`, not from `promptParts.security.workingHours`.

See `references/prompt-builder-vs-cadence-boundaries.md` for the full separation of concerns, the duplicate that was removed May 30, 2026, and the design rules for where to put new scheduling constraints.

## 15. Structured Prompt Builder (May 2026 — Implemented)

The Prompt Builder is the frontend system for authoring cadence system prompts. It replaces the old single-textarea editor with a structured 8-tab modal that lets Greg compose prompts from constituent parts, validate for contradictions, and save directly.

### Data Model

The cadence `config` JSON gains a `promptParts` key alongside the existing `systemPrompt`:

```json
{
  "systemPrompt": "Compiled output — what the LLM actually sees at send time",
  "promptParts": {
    "objective": "North star for the cadence",
    "brandPersonality": {
      "tone": "warm|formal|casual|funny",
      "style": "direct|consultative|storytelling|provocative",
      "language": "English|Hinglish|Hindi",
      "adaptLanguage": true|false,
      "formality": 1-5,
      "vocabulary": "Free text describing preferred vocab and phrases",
      "phrases": "",
      "personality": "Free text describing Ava's persona and character"
    },
    "sectorSpecific": {
      "valueProps": "...",
      "caseStudies": "...",
      "competition": "...",
      "customers": "...",
      "pricing": "...",
      "fomo": "...",
      "deckRef": "..."
    },
    "security": "Guardrails, injection protection, FAQs",
    "channelSpecific": {
      "whatsapp": "WhatsApp style + sequential logic (free-form)",
      "email": "Email style + structure (free-form)",
      "call": "Call script structure (free-form)"
    }
  }
}
```

**Key design decision:** `systemPrompt` stays as the compiled output. All existing code that reads `systemPrompt` (message generation, preview, etc.) continues to work unmodified. The `promptParts` are only used by the builder UI and the validate/compile pipeline.

### Frontend: 7-Tab Modal

Located in `cadence_template.py` (inline HTML/JS/CSS). The modal has a tab bar with 7 tabs (Objective was removed and moved to a per-template tile on the main page):

| Tab | Content |
|-----|---------|
| 🔗 **Aggregated** | Shows the compiled prompt + contradiction results. Section chips filter which parts of the compiled prompt to highlight |
| 🎨 **Brand & Personality** | Tone chips (9 options), Style/select, Vocabulary/select, Language chips (5 options), Communication Style/textbox, Personality/textbox |
| 📊 **Sector-Specific** | 7 textareas: value props, case studies, competition, customers, pricing, FOMO, KB deck reference |
| 🛡 **Security** | Monospace textarea for guardrails |
| 📱 **WhatsApp** | Free-form textarea |
| ✉️ **Email** | Free-form textarea |
| 📞 **Call** | Free-form textarea |

**Tab switching:** Event delegation on `.prompt-editor-tab` click → `switchTab(tabId)`. Active tab gets `.active` class, corresponding `.prompt-editor-body` gets `.active`. Builder opens on Brand tab by default (since Objective tab was removed).

**Pre-fill on load:** When `doLoadTemplate()` runs, it calls `prefillFromInduction()` after a 300ms delay if `globalPromptParts` are empty. The function fetches `GET /api/cadence/prefill`, splits: objective → `t.objective`, rest → `globalPromptParts`, loads both, saves, and calls `assembleSystemPrompt(t)` to merge objective into the compiled system prompt.

**Preview in sidebar:** The collapsed preview (`#systemPromptPreview`) shows the first 120 chars of `t.objective` (or `t.systemPrompt` as fallback).

**Architecture bar** numbering changed: Brand=1 → Sector=2 → Security=3 → WhatsApp=4 → Email=5 → Call=6 → Final Prompt=F (no Objective step, no Objective tab).

### Backend: Validate & Compile

**Endpoint:** `POST /api/cadence/validate`

Takes `{template_id, promptParts}` and:
1. Builds a structured prompt with all components labeled by section
2. Sends to `call_llm()` asking it to:
   - **TASK 1 — Contradiction check:** Find logical contradictions or ambiguities between sections
   - **TASK 2 — Compile:** Combine all sections into one coherent system prompt in order: Personality → Objective → Sector → Security → Channels
3. Returns `{contradictions: [...], compiled_prompt: "..."}` 

**LLM prompt structure:**
```
Cadence Type: {cold|inbound|nurture}

## Prompt Components
### 1. Objective
### 2. Brand & Personality
### 3. Sector-Specific
### 4. Security & Guardrails
### 5. Channel: WhatsApp
### 6. Channel: Email
### 7. Channel: Call

## Your Tasks
TASK 1 — Contradiction Check
TASK 2 — Compile the final system prompt

Respond ONLY with valid JSON:
{
  "contradictions": [...],
  "compiled_prompt": "..."
}
```

**Pitfall:** The LLM prompt uses f-string formatting. Double-check that curly braces in the response format instruction are escaped as `{{` and `}}` to avoid `KeyError` from Python's `str.format()`.

### Backend: Pre-fill

**Endpoint:** `GET /api/cadence/prefill`

Returns `{prefill: {cold: {...}, inbound: {...}, nurture: {...}}}` — generated for all 3 cadence types from:
- Existing brandVoice settings (tone, formality, nonos)
- Existing systemPrompt (first paragraph → objective)
- Existing steps (channel descriptions → channel-specific sections)
- Hardcoded defaults for sector-specific content (extracted from induction data)
- Hardcoded security template (English-only, guardrails, injection protection)
- Hardcoded channel style guides (WhatsApp short/punchy, email with subject line, call talking-points)

### Save Flow

"💾 Save & Close" in the modal:
1. Calls `collectPromptParts()` → reads all tab inputs into a promptParts object
2. Updates `t.systemPrompt` and `TEMPLATES[k].systemPrompt` on ALL templates in localStorage
3. Calls `saveData()` to persist to localStorage
4. POSTs to `/api/cadence/publish-global` with `{promptParts, compiled_prompt}` — writes to ALL three templates in the DB

**Critical bug fixed (June 2026):** Previously sent `template_id: 'global'` to `/api/cadence/publish` which the backend rejected (only accepts cold/inbound/nurture). The publish silently failed — data stayed in localStorage, DB never got updated. The LLM generated from an empty systemPrompt, producing generic emails.

### Publish Cadence Button Behavior

The main **"Publish Cadence"** button on the cadence page now does two things in one click:
1. Publishes the current template's steps/conditions/brandVoice via `/api/cadence/publish` (existing)
2. **Also** calls `/api/cadence/publish-global` if the template has a compiled systemPrompt with content — fans out to all three templates (new)

This means either Save & Close OR Publish will push the global prompt to the server.

### CSS Architecture

The modal uses a shared overlay pattern (`.prompt-editor-overlay`) consistent with the step picker and confirm dialogs. Key classes:
- `.prompt-expand-btn` — "✎ Open Builder" button in the cadence page
- `.prompt-preview-box` — collapsed preview box in the sidebar
- `.prompt-editor-tab.active` — active tab bottom-border highlight
- `.prompt-editor-body.active` — visible tab content
- `.sec-input` — structured input textareas (variants: `.short`, `.tall`, `.code`, `.monospace`)
- `.bp-*` — Brand & Personality structured inputs (select, range, toggle)
- `.prompt-section-chip.active` — aggregated tab filter chips
- `.prompt-aggregated-prompt` — read-only compiled prompt display
- `.prompt-contradiction-item` — yellow warning box for detected issues
- `.prompt-no-contradictions` — green success box

### Prompt Parts Granularity

The Brand & Personality tab uses structured HTML inputs (selects, range slider, checkbox) instead of free-form text for certain fields:
- **Tone:** select (warm/formal/casual/funny)
- **Style:** select (direct/consultative/storytelling/provocative)
- **Language:** select (English/Hinglish/Hindi)
- **Adapt language:** checkbox
- **Formality:** range slider (1-5) with live label update (`oninput="..."`)
- **Vocabulary:** free-form textarea

The Sector-Specific tab uses 7 separate textareas (not one big blob) so each can be individually edited and the compile LLM gets cleanly labeled sections.

### Knowledge Base Integration

The Sector tab has a "Knowledge Base Reference" field (`deckRef`) where Greg can paste references to specific decks or KB documents. This is a free-form textarea — the KB file/upload system is separate. The compiled prompt includes this text verbatim.

### Comparison: Old vs New

| Aspect | Old (pre-May 2026) | New |
|--------|-------------------|-----|
| Input | Single monospace textarea | 7 tabs with structured inputs |
| Formatting | Raw text | Formatted preview with LLM compilation |
| Validation | None | LLM contradiction check |
| Save | Only via "Publish Cadence" | Direct "Save & Close" |
| Sections | Flat text | Brand, Sector, Security, Channels (+ per-template Objective on main page) |
| Pre-fill | None | Auto-fills globalPromptParts from induction, splits objective per-template |
| Channel prompts | Built into step desc | Separate tab per channel |
| Objective authoring | Tab in builder | Per-template tile on Outreach Central page — inline `contenteditable` div, `startObjectiveEdit()` replaces `prompt()` pop-up, stored as `t.objective` |

### Future
- Move the Validate & Compile to auto-trigger on tab switch (debounced)
- Add KB file upload/selector for the `deckRef` field
- Add "Reset to Induction Defaults" button per section
- The old `TONE_PREVIEW` string in server.py should be removed in favor of a proper dict lookup once all field types are settled

### ⚠️ Pitfall: `saveCurrentState()` crashes with dead DOM references

**Problem:** When UI elements are removed or restructured (e.g., brand voice chips, `systemPromptInput` textarea), `saveCurrentState()` in `cadence_template.py` crashes with `TypeError: Cannot read properties of null`. This blocks template switching via `selectTemplate()` because `doSwitchTemplate()` calls `saveCurrentState()` first.

**Symptoms:**
- Template cards appear in the DOM but Inbound and Nurture are unclickable
- User must refresh page to reset state
- Console shows `TypeError: Cannot read properties of null (reading 'value')` at `saveCurrentState`

**Fix:** Every time you remove UI elements from `cadence_template.py`, check `saveCurrentState()` for references to those elements (especially `document.getElementById('systemPromptInput')`, `document.querySelector('#toneChips .tone-chip.active')`, `#nonosContainer`, `#formalitySlider`, and any `t.brandVoice.*` references). Remove the dead lines.

**Prevention pattern:** `saveCurrentState()` should only save data for elements that still exist in the DOM:
1. Steps — always needed (timing + desc textareas)
2. Conditions + Stop Conditions — always needed (checkboxes)
3. Brand voice — ONLY if the brand voice UI still exists; remove if moved to a different editor
4. System prompt — ONLY if the raw textarea still exists; remove if using Prompt Builder

## Prompt Builder Debugging

Also documents the **design boundary between prompt builder (content) and cadence conditions (behavior)** — see `references/prompt-builder-vs-cadence-boundaries.md`

## Prompt Builder Debugging

See `references/prompt-builder-debugging.md` for patterns covering duplicate ID conflicts, scoped DOM queries, prefill serialization, guard logic, and three-file propagation.

See `references/cadence-template-restoration.md` for the recovery procedure when a cadence template's steps, conditions, brandVoice, or systemPrompt are corrupted/empty.

## See Also  
- `references/actionitems-notification-system.md`  
- `references/ava-error-handling-protocol.md` — Error Handling Protocol for Ava: how tool errors are translated to agentic, action-oriented user responses instead of raw error dumps  
- `references/cadence-debugging-failure-modes.md` — Complete failure mode matrix with step-by-step diagnostic procedures  
- `references/playbook-custom-actions-and-at-mentions.md` — Custom actions, @-mention integration, double-quote fix, main page summary
- `ara-agent-learning-loop` — full learning flywheel architecture, skills injection into generation paths, segment-aware skill filtering
- `ara-tenant-specific-infrastructure` — tenant-configurable segments and platform-level architecture decisions

## Related Skills

- **ara-cadence-prompt-management** — Managing outbound cadence prompts across ARA's three storage layers (prompt_templates.json, DB promptParts, system prompt). Covers the update pipeline, content architecture rules, the 3-block first-message structure, and common pitfalls.

## To test

1. `cd /Users/greg/ara && ./venv/bin/python server.py`
2. Navigate to `/cadence` — verify step cards show timing controls only (no desc textarea)
3. Click ⟳ Regenerate on a step — verify LLM generates from system prompt + step desc
4. Publish a cadence — verify `systemPrompt` stored, no `channelPrompt` in step objects
5. Trigger an inbound WhatsApp reply for a `new` lead — should auto-advance to `engaged`
6. Call evaluate_qualification via Ava's chat or direct API test
7. Check ActionItems for human notifications
