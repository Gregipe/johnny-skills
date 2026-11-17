# Prompt Builder vs Cadence Template Boundaries

## Separation of Concerns

ARA has two distinct configuration surfaces for cadences. **They manage different layers** — content vs behavior. Mixing them causes duplication and confusion.

| Layer | Owned by | What it configures | Where |
|-------|----------|-------------------|-------|
| **Content** | Prompt Builder (`prompt_builder_template.py`) | What Ava says — brand voice, sector intel, security guardrails, channel-specific guidance, objection handling, FAQs | Saved to `globalPromptParts` in browser, persisted to DB as `config.promptParts` |
| **Behavior** | Cadence Template Conditions (`cadence_template.py`) | When Ava sends — working hours, weekdays, Saturday/Sunday, stop conditions (meeting booked, opted out, not interested) | Saved to `t.conditions` / `t.stopConditions` in browser, persisted to DB as `config.conditions` |

## The Duplicate That Was Removed

**Before May 30, 2026:** The Security tab of the prompt builder contained a "Working Hours & Compliance" block with 4 checkboxes:

- Working hours (9AM–6PM IST) — id: `pe_workingHours`
- Weekdays only — id: `pe_weekdays`
- Saturday — id: `pe_saturdaySaturday`
- Sunday — id: `pe_sundaySunday`

These were saved as `security.workingHours` and `security.weekdays` in `promptParts`.

**Problem:** The runtime (`server.py:2260`) reads conditions from `template.get("conditions", {})` — the cadence-level conditions — NOT from `promptParts.security.workingHours`. The prompt builder fields were dead weight: saved but never read at execution time.

**Fix (May 30, 2026):** Removed the duplicate from `prompt_builder_template.py`:
- HTML block removed from Security tab
- "Working hours" entry removed from Guardrails Summary sidebar
- Save/load JS for `pe_workingHours`, `pe_weekdays` etc. removed from `collectPbParts()` and the load function

## Canonical Location for Scheduling Conditions

Working hours and day-of-week constraints live in **each cadence template's `conditions` object**:

```javascript
// In cadence_template.js — Reachout Conditions section
t.conditions = {
    workingHours: document.getElementById('condWorkingHours').checked,  // 9AM-6PM IST
    weekdays: document.getElementById('condWeekdays').checked,         // Mon-Fri
    saturday: document.getElementById('condSaturday').checked,
    sunday: document.getElementById('condSunday').checked
};

// Stop Conditions (also per-template)
t.stopConditions = {
    meetingBooked: document.getElementById('stopMeetingBooked').checked,
    optOut: document.getElementById('stopOptOut').checked,
    notInterested: document.getElementById('stopNotInterested').checked
};
```

**Runtime consumption** (server.py line ~2260):
```python
conditions = template.get("conditions", {})
# Only applied to email and call channels (not WhatsApp):
if channel in ("email", "call"):
    fire_at = _next_working_time(fire_at, conditions)
```

## What Belongs in Cadence Steps (Not Prompt Builder) — Sequence Tab Removed

**May 30, 2026:** The Sequencing Strategy tab was removed from the Prompt Builder slide-over. It was a static timeline visualization of channel order (WhatsApp → Email → Call) that duplicated what's already configurable in the cadence steps area below.

**Why:** Channel order, timing (delay_hours, repeat_count, interval_hours), and step setup belong in the cadence steps area — the same UI where the user adds/removes/reorders steps, sets delays and repeats, and writes step descriptions. The Prompt Builder's Sequencing tab was a read-only echo of that data with no interactive controls. It added cognitive overhead (\"I see the sequence here but configure it there\") without utility.

**Cleanup:**
- Removed sidebar nav item (Sequencing Strategy)
- Removed arch step button (S between Call and F)
- Removed tab content (timeline visualization with pb-tl-* CSS)
- Removed `Sequence` chip from the Final tab's section chips filter
- Removed all `.pb-timeline` CSS rules
- Removed `Sequence` from the OUTREACH TEMPLATE preview bar (`prompt-overview` chips)
- Removed "| Sequencing" from the description tagline

**Design boundary rule:** The only configuration surface for scheduling (channels, timing, repeats) is the cadence steps area on the main `/cadence` page. The Prompt Builder manages content — what Ava says per channel, not the order/timing of sends.

## Design Rule

**When adding a new scheduling or behavioral constraint** (e.g., "only send between 10AM-4PM", "skip Sundays", "don't send on Indian public holidays"):

1. Add it to the **cadence template's conditions** in `cadence_template.py` — a checkbox in the Reachout Conditions section
2. Add it to the `conditions` object in `saveCurrentState()`
3. Add it to the `renderCurrentTemplate()` load path
4. Read it from `template.get("conditions", {})` in `server.py`

**Do NOT** add it to the prompt builder's Security tab. That tab is for **content guardrails** (injection prevention, restricted claims, escalation rules, FAQs). Scheduling is behavioral, not content.

## What Belongs in Prompt Builder Security Tab

| Field | Purpose |
|-------|---------|
| Prompt Injection Prevention | Guardrails against prompt injection attacks |
| Restricted Claims | What Ava must never claim (e.g., "never guarantee results") |
| Escalation Rules | When to escalate to human |
| FAQs & Approved Answers | Pre-approved responses to common questions |

These are **content guardrails** — they shape what Ava says, not when she says it.
