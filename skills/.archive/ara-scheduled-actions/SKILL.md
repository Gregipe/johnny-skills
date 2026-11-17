---
name: ara-scheduled-actions
description: ARA's scheduled actions system — auto-firing WhatsApp/email/call reminders per lead, cadence engine, stage advancement tools, silence resume protocol

> **NOTE:** This skill has absorbed content from `ara-cadence-prompt-management`. See the "Cadence Engine" section for prompt management details.

---

# ARA Scheduled Actions System

## Core Data Models

### ScheduledAction
```python
# database.py
class ScheduledAction(Base):
    __tablename__ = "scheduled_actions"
    id, tenant_id, lead_id, action_type (whatsapp/email/call_reminder/internal_note),
    status (pending/firing/completed/failed/cancelled), scheduled_at, fired_at,
    payload (JSON), channel, retry_count (max 3), max_retries, last_error, next_retry_at
```

### CadenceConfig
```python
# database.py
class CadenceConfig(Base):
    __tablename__ = "cadence_configs"
    id, tenant_id, template_id (cold/inbound/nurture), config (JSON — full template),
    published_at, updated_at
```

### ActionItem (Human Notifications)
```python
# database.py
class ActionItem(Base):
    __tablename__ = "action_items"
    id, tenant_id, action_type (suggest_deal/escalate/stage_change/review_qualification/
                                 meeting_request/review_reengagement),
    title, description, ref_type (lead/deal/conversation), ref_id,
    status (open/dismissed/resolved), created_at, resolved_at
```

## Scheduler Daemon

`_run_scheduler()` in `server.py` — background thread polling every 30s, started in `lifespan`.

```
Loop every 30s:
  1. Fetch due actions (scheduled_at <= now, status=pending/firing)
  2. Fetch retry-eligible actions (failed, next_retry_at <= now, retries < max)
  3. For each action:
     a. Mark "firing"
     b. Execute via _execute_action() — dispatches by action_type
     c. On success → "completed", fired_at = now
     d. On failure → increment retry_count, exponential backoff (60s→300s→900s)
        If max retries exceeded → "failed", create LearningNotification
  4. _check_dormant() — 30-day inactivity → stage=dormant
  5. _check_silence_resume() — 7-day silence follow-ups
```

### Execution Channels (`_execute_action`)

| action_type | Mechanism | Requires |
|-------------|-----------|----------|
| `whatsapp` | `wa.send_message_sync(lead.phone, message_text)` via `_execute_action()` | Lead phone + WhatsApp connected |
| `email` | `send_via_gmail_api(tokens, lead.email, subject, body)` | Lead email + Gmail OAuth tokens |
| `call_reminder` | Creates LearningNotification for dashboard bell | Lead assigned |
| `internal_note` | Creates LearningNotification with title+message | — |

## Cadence Engine

Turns a configured sequence of steps (from the UI or API) into concrete ScheduledAction records.

### How it works (`_schedule_cadence_for_lead`)

1. **Gate check** — Only schedules for `new`/`reached_out` leads. Skips `engaged`+ (Ava handles agentically), `dormant`, `lost`.
2. **Load config** — Reads published `CadenceConfig` for the lead's `cadence_type` (cold/inbound/nurture).
3. **Duplicate check** — If lead already has pending/firing actions, skip (don't double-schedule).
4. **Walk steps** — For each step, compute fire time from `day * 24h + delay_hours` offset from now.
5. **Interpolate** — Replace `{{name}}`, `{{first_name}}`, `{{company}}`, `{{city}}`, `{{industry}}`, `{{phone}}`, `{{email}}` with lead data via `_interpolate_message()`.
6. **Working hours** — Email/call steps shifted to next 9AM workday via `_next_working_time()`. WhatsApp allowed anytime.
7. **Cascade repeat intervals** — Each repeat accumulates on the ADJUSTED time (not raw UTC), so working hours don't collapse all repeats to the same slot. For email/call, interval is added to `fire_at_adj` (IST-aware), not `fire_at` (raw UTC):
   ```python
   fire_at = now + timedelta(hours=delay_hours)
   for r in range(repeat_count):
       if channel in ("email", "call"):
           if r == 0:
               fire_at_adj = _next_working_time(fire_at, conditions)
           else:
               fire_at_adj = _next_working_time(fire_at_adj + timedelta(hours=interval_hours), conditions)
       else:
           fire_at_adj = fire_at
           fire_at += timedelta(hours=interval_hours)
       # Create ScheduledAction with fire_at_adj
   ```
   **Why:** The old code accumulated `fire_at += timedelta(hours=interval_hours)` in raw UTC for ALL channels. After ~6 hours of 1h-interval emails starting at 18:00 IST, `fire_at` wrapped to the next UTC day. All subsequent repeats landed before 9AM IST, and `_next_working_time` clamped them all to 9:00 sharp. The fix: for email/call, accumulate on `fire_at_adj` (already in IST working hours) so intervals are IST-aware — 1h interval means 1h in working time, wrapping cleanly across days.
8. **Day-of-week conditions** — `_next_working_time` now respects `saturday` and `sunday` fields from the template conditions JSON. Logic:
   - If `saturday` is explicitly `true` → Saturday is a working day
   - If `saturday` is explicitly `false` → Saturday is blocked
   - If `saturday` is not set → falls back to `weekdays` setting
   - Same for `sunday`
   This allows templates to enable Saturday outreach while keeping Sunday blocked, or any other combination.

### Cadence Mapping (Auto-Assignment)

```python
CADENCE_MAPPING = [
    (lambda s, st: s in ('form','meta','google','referral') and st != 'dormant', 'inbound'),
    (lambda s, st: st in ('dormant','lost'), 'nurture'),
]
# Fallback: 'cold'
```

On lead creation, `determine_cadence()` runs. Manual override sets `cadence_auto_assigned='no'`.

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/cadence/config` | GET | Returns current published cadence config |
| `/api/cadence/preview` | POST | LLM-generated preview of a step's message |
| `/api/cadence/publish` | POST | Publish/update cadence steps (from UI) — replaces entire config |
| `/api/cadence/trigger` | POST | Bulk-trigger cadence for leads in specific stages |
| `/api/cadence/trigger/lead/{lead_id}` | POST | Trigger/retrigger for one lead (cancels old, schedules new) |

### Ava Tool-Created Scheduled Actions (May 2026 + June 2026)

Ava can now create ScheduledAction records directly via tool calls. These are one-off actions (not cadence steps) created on-demand:

| Ava Tool | ScheduledAction Created |
|----------|------------------------|
| `schedule_message(lead_name, message, delay_minutes)` | `action_type="whatsapp"`, `scheduled_at=now+delay` |
| `schedule_email(lead_name, subject, body, delay_minutes)` | `action_type="email"`, `scheduled_at=now+delay` |
| `send_email(lead_name, subject, body)` | Same as schedule_email with `delay_minutes=1` (fires almost immediately) |
| `send_whatsapp_to_owner(message, delay_minutes)` | `action_type="whatsapp_to_owner"`, `lead_id=None`, `scheduled_at=now+delay` when `delay_minutes > 0`; sends instantly when omitted/0 |
| **`set_cron` 🆕** | **Recurring action. Stores `{"cron": {"frequency": "daily"\|"weekdays"\|"weekly", "time": "18:30", "title": "..."}}` in payload. Scheduler reschedules after each fire.** |
| **`set_reminder` 🆕 (June 15)** | **Creates ActionItem + ScheduledAction linked pair. Lead-scoped with ref_type/ref_id. `action_type="whatsapp_to_owner"`, `scheduled_at=due_at`. Notification: `✨ *Ava :*\n\n⏰ **Reminder:** {title} ({lead.name})`** |
| **`create_action_item` 🆕 (June 15)** | **Same pattern as set_reminder when `delay_minutes` or `due_at` provided. Otherwise creates action-item-only.** |

These are picked up by the same scheduler daemon — no new infra needed.

### Recurring Cron Actions (June 2026)

The `set_cron` tool creates a ScheduledAction with a cron config stored in the payload:
```python
payload = {"message": "...", "cron": {"frequency": "daily", "time": "18:30", "title": "Daily Summary"}}
```

**`__morning_briefing__` Dynamic Content** — The scheduler supports a special message value `__morning_briefing__` that generates dynamic content from live DB data at fire time (see section below for implementation).

**Python 3.12 Scoping Crash (June 10, 2026)** — Fixed with local import before use.

### `__morning_briefing__` Dynamic Content Implementation

The scheduler generates dynamic content from live DB data at fire time when the cron message is set to `__morning_briefing__`:

**In `_execute_action()`, `whatsapp_to_owner` handler (line ~7913):**

```python
if message == "__morning_briefing__":
    items = db.query(ActionItem).filter(
        ActionItem.tenant_id == action.tenant_id,
        ActionItem.status.in_(["open", "in_progress"])
    ).order_by(ActionItem.created_at.asc()).limit(15).all()
    lines = ["☀️ Good morning, Greg! Here are your outstanding items today:"]
    if items:
        for item in items:
            lines.append(f"  ⚪ {item.title}")
    else:
        lines.append("  Nothing outstanding — you're all caught up!")
    lines.append("")
    lines.append("Say 'what's the pipeline' for deals or 'summarize my day' for a full run-down.")
    message = "\n".join(lines)
```

**Setting up:** Ava calls `set_cron` with `message="__morning_briefing__"`. The tool description at line ~5172 mentions this option.

**Pitfall:** `to_ist()` returns a string, not a datetime. Don't call `.isoformat()` on it.

### Frequency validation
The `set_cron` tool only accepts `daily`, `weekdays`, or `weekly`. Any other value (including "monthly," "hourly," etc.) returns an error immediately:
```python
if frequency not in ("daily", "weekdays", "weekly"):
    return "Error: 'frequency' must be one of: daily, weekdays (Mon-Fri), weekly"
```

In `_run_scheduler()`, after a successful execution, the code checks for a cron config:
```python
_cron_cfg = action.payload.get("cron")
if _cron_cfg and isinstance(_cron_cfg, dict):
    _freq = _cron_cfg.get("frequency", "daily")
    _h, _m = (int(x) for x in _cron_cfg.get("time", "18:30").split(":"))
    # CRON TIME IS IN IST — convert cron time to UTC for storage
    _now_ist = datetime.now(IST_TZ)
    _next_ist = _now_ist.replace(hour=_h, minute=_m, second=0, microsecond=0)
    _safety = 0
    while _next_ist <= _now_ist:
        if _freq in ("daily", "weekdays"): _next_ist += timedelta(days=1)
        elif _freq == "weekly": _next_ist += timedelta(days=7)
        else: _next_ist += timedelta(days=1)
        _safety += 1
        if _safety > 365:
            raise Exception(f"Cron reschedule exceeded safety limit (freq={_freq})")
    if _freq == "weekdays":
        while _next_ist.weekday() >= 5:
            _next_ist += timedelta(days=1)
    _next = _next_ist.astimezone(timezone.utc).replace(tzinfo=None)
    action.scheduled_at = _next
    action.status = "pending"  # ← rescheduled, not completed
else:
    action.status = "completed"  # ← one-shot, normal path
```

**CRITICAL: Cron times are IST, but scheduled_at is stored in UTC.** The user sets "06:30" meaning 6:30 AM IST. The `_next_ist` computation works in IST, then converts to UTC for the DB: `06:30 IST → 01:00 UTC`. Without this conversion, `06:30 UTC = 12:00 IST` — actions fire 5.5 hours late. This has been broken twice. Always use the IST-first pattern above.

**Safety limit:** The scheduler's reschedule while-loop has a counter to prevent infinite loops from invalid frequencies (though the tool now validates upfront, the scheduler guard exists as defense-in-depth):

```python
_safety = 0
while _next_ist <= _now_ist:
    if _freq in ("daily", "weekdays"):
        _next_ist += timedelta(days=1)
    elif _freq == "weekly":
        _next_ist += timedelta(days=7)
    else:
        _next_ist += timedelta(days=1)  # fallback for unknown frequency
    _safety += 1
    if _safety > 365:
        raise Exception(f"Cron reschedule exceeded safety limit (freq={_freq})")
```

**No schema migration needed** — cron config lives entirely in the JSON payload column. One action row perpetually reschedules itself.

### Deal Stage Sync

`_sync_deal_stage_from_lead()` — rewritten June 2026 for bidirectional mirroring:

- **One lead on deal**: deal mirrors that lead exactly (forward AND backward). Stage order: `new → reached_out → engaged → qualified → meeting_booked`.
- **Multiple leads on deal**: deal = highest stage among all non-archived attached leads. Backward moves only affect the deal if they drop the highest stage.
- Called after every stage change via `update_lead_stage` tool and inbound-message handlers.

**Important:** Ava-created actions use `action_type` and `channel` that match the existing `_execute_action()` dispatcher. The scheduler doesn't distinguish between cadence-created and Ava-created actions.

### `send_whatsapp_to_owner` with Delay (June 2026)

`send_whatsapp_to_owner` originally only supported instant sends (`wa.send_message_sync` directly). Added `delay_minutes` parameter:
- **`delay_minutes=0` (default):** Sends immediately to admin phone via `wa.send_message_sync`
- **`delay_minutes > 0`:** Creates a `ScheduledAction` with `action_type="whatsapp_to_owner"` and `lead_id=None`. The scheduler picks it up at the scheduled time.

The `_execute_action()` handler for `whatsapp_to_owner` queries the admin user by `User.role == "admin"` within the tenant, then calls `wa.send_message_sync(admin.phone, "✨ *Ava :*\n\n" + message)`. As of June 15, this matches the coaching reply format. This is a separate code path from the lead-targeted `whatsapp` action type — no lead_id is required since the target phone is derived from the admin user record at fire time.

### Notification Format (June 15, 2026)

Owner notifications now use the same `✨ *Ava :*` header as all coaching replies, with bold action labels:

```
✨ *Ava :*

⏰ **Reminder:** Set Timing for Chat (Dinesh Nagar)
```

Previously the format was bare `"Ava: " + message`. The change aligns with the coaching handler format at server.py line 9718.

## Stage Advancement Tools (Ava-Called)

New in May 2026. Ava calls these via `[TOOL_CALL: ...]` after evaluating conversations.

### `evaluate_qualification`

Args: `lead_name`, `assessment`, `fits_icp` (true/false/"uncertain"), `confidence` (high/medium/low)

Logic:
- `fits_icp=true + confidence=high` → auto-advance to `qualified`, ActionItem notification (✅)
- `fits_icp=true + confidence=medium` → advance to `qualified`, flag human (🔔)
- `fits_icp=false + confidence=high/medium` → move to `lost`, cancel all pending actions (🚫)
- `confidence=low` → flag human review (❓), no stage change

Design rule: Be BROAD. Only disqualify on complete mismatch. KB + induction are the source of truth.

### `mark_meeting_booked`

Args: `lead_name`, `meeting_details` (e.g. "Thursday 3pm, demo call")

Logic:
- Moves lead to `meeting_booked`, cancels all pending actions
- Syncs deal stage via `_sync_deal_stage_from_lead()`
- Creates `ActionItem` with action_type `meeting_request` — notifies human
- Ava's ceiling — human takes over after this

Design rule: Only use when lead EXPLICITLY agrees to meet. "Call me later" ≠ meeting. If human responds: "My manager has yet to confirm — apologies — would you have a few more slots?"

## Stage Transitions (Code-Enforced)

### Auto-Cancellation on Re-Engagement

When inbound message arrives (`_handle_inbound_whatsapp`), all pending/firing actions for that lead are cancelled. Then:
- `new/reached_out` → `engaged`
- `dormant` → check deal: if deal was at `qualified`/`meeting_booked` → restore to `qualified`, else `engaged`
- `lost` → create `ActionItem` for human review, don't auto-advance

### Deal Stage Sync

`_sync_deal_stage_from_lead()` — when a lead advances, push the deal stage forward (up to `meeting_booked`). Forward-only, capped. Called after every stage change.

### Lost Stage Handling

When stage set to `lost` (via API or `evaluate_qualification`):
- All pending actions auto-cancelled
- Excluded from auto-dormant checks
- Excluded from cadence scheduling
- Re-engaging lost leads → flagged for human review (Greg must approve)

## 7-Day Silence Resume Protocol (once per day)

`_check_silence_resume()` in `server.py:~8264` — once-per-day follow-up engine.

### How it works

1. **Rate-limited to once per day** via timestamp file (`/tmp/ara_last_silence_check`). Guards against the 30-second scheduler tick.
2. **Lead age gate:** only targets leads with `created_at <= now - 7 days`. Brand-new leads with stage "engaged" are excluded.
3. Polls `engaged`/`qualified` leads with no conversations in last 7 days
4. If silent AND no pending follow-up scheduled → create one
5. Channel alternation: email → WhatsApp → email → WhatsApp (based on count of previous 30-day follow-ups)
6. Message: friendly, low-pressure, no-spam ("Hi X, just checking in...")
7. Fires within 1 hour via ScheduledAction (`scheduled_at = now + timedelta(hours=1)`)

### ⚠️ Firehose Pitfall (June 15, 2026)

**35 messages were delivered to one lead in 5 minutes because of this function, not the cadence engine.** The cascade:

1. Prashant Rai was created with `stage = "engaged"` — matched the query immediately
2. New lead had zero conversations → silence check passed
3. Follow-up created with `scheduled_at = now + 1h`
4. IST timezone bug made the 1h-ahead date appear due → fired in the same tick
5. Next tick (30s later): previous follow-up was `completed`, not `pending` → guard bypassed → created another
6. Loop repeated 35 times

**Fixes applied (June 15):**
- **Rate-limit:** `_check_silence_resume()` writes a timestamp file and skips if less than **24 hours** (once per day) since last check. Originally set to 1 hour — Greg explicitly requested once per day.
- **Age gate:** `Lead.created_at <= silence_cutoff` added to the query — lead must be 7+ days old
- **Pending guard** already existed but was only effective when dates fire correctly (not the IST-broken state)

**Code (rate-limit + age gate):**
```python
import os
_LAST_SILENCE_CHECK_FILE = "/tmp/ara_last_silence_check"
if os.path.exists(_LAST_SILENCE_CHECK_FILE):
    last = datetime.fromisoformat(open(_LAST_SILENCE_CHECK_FILE).read().strip())
    if (now - last).seconds < 86400:  # once per day
        return

for lead in db.query(Lead).filter(
    Lead.stage.in_(["engaged", "qualified"]),
    Lead.tenant_id == TENANT_ID,
    Lead.created_at <= silence_cutoff,  # Lead must be 7+ days old
).all():
    ...
# After loop: open(_LAST_SILENCE_CHECK_FILE, "w").write(now.isoformat())
```

## Ava Prompt Integration

Two prompts carry the cadence/post-engagement rules:

### `AVA_AUTO_SYSTEM_PROMPT` (WhatsApp auto-response)
- **After-Conversation Actions** — evaluate qualification, nudge toward meeting, channel switching
- **Channel Switching** — template-silent rule, stay in preferred channel, migrate to email, WhatsApp nudge if email >48h silent, consistent messaging

### `AGENT_SYSTEM_PROMPT_BASE` (Dashboard chat)
- **Post-Engagement Behavior** — same rules in the chat interface

### `AGENT_TOOL_SCHEMA`
- Tools 12-13: `evaluate_qualification` and `mark_meeting_booked` with full descriptions
- Confirmation prompt includes both tools in the data-modifying list

## Key Design Decisions

| Decision | Why |
|----------|-----|
| **Code-led, not markdown-rules** | Stage transitions are deterministic logic, not user-configurable rules. Qualification is LLM-judged within code guardrails. |
| **Engaged+ excluded from cadences** | Once a lead responds, templates are void. Ava handles agentically toward meeting booking. |
| **Auto-cancel on any inbound** | Prevents stale messages from firing after a lead has re-engaged. |
| **ActionItems for human notifications** | Lightweight DB model, no external dependency. Exportable as JSON. Telegram/WhatsApp delivery deferred. |
| **Silence resume is code-enforced** | Not LLM-judged — the pattern is simple enough (7-day threshold, alternating channels). |
| **Retry with backoff** | 60s → 300s → 900s, max 3. Permanent failure alerts human via LearningNotification. |

## Lead Detail Scheduled Actions Display

When viewing a lead's detail panel in the dashboard, the `cadenceHTML()` function now shows upcoming scheduled actions. This involves both backend and frontend changes.

### Backend: Single Lead API

The `GET /api/leads/{lead_id}` endpoint must return scheduled action data:

```python
# Query next action
next_action = db.query(ScheduledAction).filter(
    ScheduledAction.lead_id == lead_id,
    ScheduledAction.status.in_(["pending", "firing"]),
    ScheduledAction.scheduled_at >= now - timedelta(hours=1),
).order_by(ScheduledAction.scheduled_at.asc()).first()

# Query all upcoming actions
upcoming = db.query(ScheduledAction).filter(
    ScheduledAction.lead_id == lead_id,
    ScheduledAction.status.in_(["pending", "firing"]),
    ScheduledAction.scheduled_at >= now - timedelta(hours=1),
).order_by(ScheduledAction.scheduled_at.asc()).all()

# In return dict:
"next_activity_at": next_action.scheduled_at.isoformat() if next_action else None,
"next_activity_type": next_action.action_type if next_action else None,
"next_activity_channel": next_action.channel if next_action else None,
"scheduled_actions": [{
    "id": a.id, "action_type": a.action_type, "channel": a.channel,
    "scheduled_at": a.scheduled_at.isoformat() if a.scheduled_at else None,
    "status": a.status,
} for a in upcoming],
```

### Frontend: `cadenceHTML()` in `static/dashboard.js`

The function already renders the cadence dropdown. Add upcoming actions below:

```javascript
function cadenceHTML(l) {
  // ... existing dropdown code ...
  
  var actionsHtml = '';
  var actions = l.scheduled_actions || [];
  if (actions.length > 0) {
    actionsHtml = '<div style="margin-top:8px">';
    actions.forEach(function(a) {
      var timeStr = a.scheduled_at ? new Date(a.scheduled_at).toLocaleString('en-US', {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'}) : '';
      var icon = a.channel === 'whatsapp' ? '💬' : a.channel === 'email' ? '✉️' : a.channel === 'call' ? '📞' : '📡';
      actionsHtml += '<div style="display:flex;align-items:center;gap:6px;font-size:11px;padding:3px 0">' +
        icon + ' <span>'+a.action_type+'</span> <span>→</span> <span>'+timeStr+'</span></div>';
    });
    actionsHtml += '</div>';
  }
  
  return dropdownHtml + (actions.length > 0 ? '<span>'+actions.length+' upcoming</span>' : '') + actionsHtml;
}
```

### Cache-Busting

When modifying `static/dashboard.js`, bump `?v=N` in `dashboard_template.py` to force browser cache refresh.

- **SQLite column type warnings** — Pyright complains about `ColumnElement[bool]` comparisons and `Column[str]` assignments throughout. These are safe at runtime — the same pattern is used everywhere in the file.
- **`_check_silence_resume()` runs every 30s** — Lightweight query, but a large lead set (>10K) might need a less frequent cadence.
- **ActionItems have no API endpoints yet** — They're created in the DB but there's no UI to view/dismiss them. See `references/known-limitations.md`.
- **Cadence config is not versioned** — Publishing overwrites. No rollback.
- **Deal stage sync now bidirectional** (June 2026) — Single lead = exact mirror forward and back. Multiple leads = highest stage. See "Deal Stage Sync" section above.
- **Engagement gate change** — Previously only `qualified`/`meeting_booked`/`dormant` were excluded from scheduling. Now `engaged` is also excluded. This means leads that replied once won't get template cadence steps — Ava handles them.
### HARD RULE: Zero Outbound Without Explicit Authorization (June 15, 2026)

**NON-NEGOTIABLE:** Cadence is NEVER auto-scheduled on lead creation or CSV import. Outbound communication from Ava only happens when Greg explicitly authorizes it or a formal cadence is explicitly scheduled via API/tool call. This rule exists because of a production incident: a cadence auto-triggered on an unassigned lead combined with a broken `_check_silence_resume()` (running every 30s due to timezone bug) delivered 35 messages to a live lead in 5 minutes.

**Code enforcement:**
- `create_lead` (server.py ~line 1177): removed `_schedule_cadence_for_lead(lead, db)` entirely
- `upload_leads_csv` (server.py ~line 1589): removed cadence scheduling loop
- Cadence can ONLY be triggered via: `POST /api/cadence/trigger/lead/{id}` or `trigger_cadence` tool call
- Memory: "HARD RULE: Zero outbound from Ava without explicit authorization"

### Scheduler Timezone Cascade (June 15, 2026)

**The bug:** A single `TypeError` (naive vs aware datetime comparison) in `_run_scheduler()` crashed EVERY tick silently for weeks. `except Exception:` swallowed it. No notifications were delivered. When the fix was deployed, all backlogged ScheduledActions fired simultaneously at ~30-second intervals (scheduler tick rate), delivering **35 messages to a live lead in 5 minutes.**

**The 35 messages came from `_check_silence_resume()`, NOT the cadence engine.** The silence resume creates follow-up messages for engaged/qualified leads with no recent conversations. The cascade: new lead (stage=engaged) → silence check creates follow-up → IST bug fires it immediately → 30s later, no pending follow-up (previous completed) → creates another → 35x loop. See "7-Day Silence Resume Protocol" section above for the fix.

**Three timezone conventions coexisted in one system:**
| Source | Timezone stored | Convention |
|--------|----------------|------------|
| Cadence (`schedule_cadence_for_lead`) | UTC (via `utcnow()`) | Aware |
| Dashboard POST /api/actions | IST (user local time) | Naive |
| Backfill (manual) | IST | Naive |

**The failed fix (IST adjustment):** Adding 5.5 hours to `now` to match IST-stored dates made UTC cadence dates (e.g., `14:10` UTC) compare as `<= 18:50` IST strings → everything fired immediately. The IST adjustment was the WRONG fix.

**The correct fix:** Normalize all storage to UTC. Store UTC. Compare UTC. Display in tenant timezone.
- `POST /api/actions`: `due_at = due_at - timedelta(hours=5, minutes=30)` (IST→UTC)
- `PATCH /api/actions`: same conversion
- Scheduler: `now = utcnow().replace(tzinfo=None)` (naive UTC)
- Display: `toLocaleString('en-US', {timeZone: TENANT_TIMEZONE})` — handles UTC→IST automatically
- Edit modal: `new Date(new Date(a.due_at).getTime() + 330*60*1000)` — UTC→IST for `datetime-local` input

**Pitfall checklist for timezone bugs:**
1. `utcnow()` returns **aware** UTC — never compare with naive datetimes
2. `datetime.fromisoformat(user_input)` is **naive** — must add timezone info
3. `except Exception:` in scheduled jobs must NEVER be bare — always log the actual error
4. String comparison of ISO dates only works when BOTH sides share the same timezone convention
5. `_check_silence_resume()` must be rate-limited — without a guard, it runs every 30s
6. `_check_silence_resume()` must exclude leads younger than 7 days — new engaged leads match the silence query
7. Any follow-up engine that creates-and-fires in the same tick can self-replicate if the pending guard is bypassed

- **Verify function signatures when debugging scheduled action failures** — May 2026 bug: `send_via_gmail_api(tokens, to, subject, body)` was called as `send_via_gmail_api(lead.email, subject, body)` — 3 args instead of 4. The first positional arg was interpreted as the `tokens` dict, making `body` appear "missing." All scheduled email actions failed silently (retried 3x then permanently failed). Root cause: the scheduler was added after the function signature changed. Always check that `_execute_action()` passes the right number and type of args for each channel's execution function, especially after refactors.
- **WhatsApp send method name** — May 2026 bug: `_execute_action()` called `wa.send(lead.phone, message)` but WhatsAppManager exposes `send_message_sync()`, not `send()`. This caused ALL scheduled WhatsApp actions to fail with `'WhatsAppManager' object has no attribute 'send'`. Fix: use `wa.send_message_sync(phone, message)` everywhere in `_execute_action()`. Search for all `wa.send(` calls in the file — there were 4 instances in server.py.
- **Midnight notification spam from `_check_action_notifications()` (fixed June 2026)** — The action reminder function runs every 30 seconds in the scheduler loop. It scans all pending human-owned action items, checks if they've been notified today, and sends WhatsApp reminders for overdue/near-due items. The dedup window is `today_start` (midnight IST). At 00:00 IST, the window resets — ALL past-due items qualify for fresh notifications, even if they were already notified earlier in the day. Result: 6 overdue action reminders delivered at midnight. Fix: add a quiet-hours gate at the top of `_check_action_notifications()`:
```python
# Suppress during sleeping hours (10 PM - 7 AM IST)
hour = ist_now.hour
if hour < 7 or hour >= 22:
    return  # silently skip — no midnight notifications
```
This is a reusable pattern for ANY notification system that runs on a high-frequency tick with a date-based dedup window. Without it, the dedup-reset-at-midnight pattern creates a predictable notification storm. `_handle_outbound_whatsapp()` opens its own `init_db()` session. When called from inside the scheduler's `_execute_action()` (which already has `db` open), the second session hits an SQLite lock. The conversation is silently lost (the function's broad `except` catches). Lead stage never transitions from `new` to `reached_out`. Fix: inline Conversation creation in `_execute_action()` using the scheduler's `db` instead:
  ```python
  from database import Conversation
  outbound = Conversation(
      lead_id=lead.id, tenant_id=TENANT_ID,
      channel="whatsapp", direction="outbound",
      subject=f"Outbound cadence to {lead.name}",
      content=message_text, summary="", sentiment="",
  )
  db.add(outbound)
  if lead.stage == "new":
      lead.stage = "reached_out"
      lead.updated_at = utcnow()
  db.commit()
  ```
  `_handle_outbound_whatsapp()` is safe ONLY outside the scheduler loop (auto-responder callback runs in its own thread/session).
- **Timezone handling for scheduled_at timestamps** — ScheduledAction timestamps are stored as naive datetime strings in SQLite (no timezone info). The API returns them via `a.scheduled_at.isoformat()`, which produces a string WITHOUT timezone suffix. When the frontend calls `new Date('2026-05-27 04:01:58.930509')`, the browser doesn't know it's UTC — it may display as local time (IST) or parse incorrectly depending on browser. Fix: append `"Z"` to the ISO string in the API response: `a.scheduled_at.isoformat() + "Z"`. Apply in BOTH `GET /api/leads/{lead_id}` (single lead detail) and `GET /api/tenants/{tenant_id}/leads` (lead list, for `next_activity_at`). Do NOT modify DB storage — only the serialized API output.
- **Timezone handling for due_at display (June 15, 2026)** — ActionItem `due_at` timestamps have the SAME issue as `scheduled_at`. After IST→UTC conversion at create time, `due_at` is stored as naive UTC. The API returns `a.due_at.isoformat()` without timezone suffix. `new Date("2026-06-16T07:30:00")` is treated as LOCAL time (7:30 AM IST = 2:00 AM UTC), NOT 7:30 AM UTC. The display shows 7:30 AM instead of 1:00 PM. Fix: append `"Z"` to ALL `due_at` serialization points (3 in server.py): `(a.due_at.isoformat() + "Z") if a.due_at else None`. The `toLocaleString(timeZone: TENANT_TIMEZONE)` call then correctly converts 7:30 AM UTC to 1:00 PM IST.
- **`to_ist()` returns a string, NOT a datetime** — `to_ist()` in server.py converts a datetime to IST and returns it as a STRING (e.g., `"2026-06-10T12:00:00+05:30"`). It does NOT return a datetime object. You CANNOT call `.isoformat()` on its return value — you'll get `AttributeError: 'str' object has no attribute 'isoformat'`. This is particularly relevant when building the `next_run` field for ScheduledActions in the Activities tab integration (see `references/activities-tab-integration.md`). If you need a string, just use `to_ist(x)` directly. If you need a datetime, use `x.astimezone(IST)` instead.
- **Working hours timezone: must check IST, not UTC** — The `_next_working_time` function checks `dt.hour` which is UTC for timezone-aware datetimes. When a lead is at 03:01 UTC (= 08:31 IST), `dt.hour < 9` evaluates true in UTC, pushes the action to 09:00 UTC (= 14:30 IST). That is wrong — working hours should be 9AM-6PM IST. Fix: convert the datetime to IST before checking, then convert back to UTC for storage:
  ```python
  IST = timezone(timedelta(hours=5, minutes=30))
  if dt.tzinfo is None:
      dt = dt.replace(tzinfo=timezone.utc)
  dt_ist = dt.astimezone(IST)
  if dt_ist.hour < 9:
      dt_ist = dt_ist.replace(hour=9, minute=0, second=0, microsecond=0)
  elif dt_ist.hour >= 18:
      dt_ist = dt_ist.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
  return dt_ist.astimezone(timezone.utc).replace(tzinfo=None)
  ```
  Apply in BOTH the weekday check AND the working hours check. New cadence triggers use the IST fix; existing scheduled actions in the DB are NOT retroactively updated.
- **`__morning_briefing__` crash on missing `priority` column (fixed June 2026)** — The morning briefing dynamic content query ordered by `ActionItem.priority.desc()` but the ActionItem model has no `priority` column (columns are: `id`, `tenant_id`, `action_type`, `title`, `description`, `ref_type`, `ref_id`, `status`, `created_at`, `resolved_at`). The `AttributeError` was caught by a broad `except`, causing the fallback message "check your dashboard" instead of the dynamic briefing. Fix: remove `.priority.desc()` from the `order_by` clause. The fallback exists to prevent a crash from taking down the entire scheduler loop, but the proper fix is to make the query work, not rely on the fallback.
- **Gmail API UnboundLocalError on plain-text emails** — May 2026. `send_via_gmail_api()` creates `msg` only inside the `if body_html or attachments:` block. If the email has neither HTML body nor attachments (plain text only), `msg` is never assigned. The `base64.urlsafe_b64encode(msg.as_bytes())` on the next line then crashes with `UnboundLocalError: cannot access local variable 'msg' where it is not associated with a value`. The scheduler retries 3x, all fail. Fix: add an `else` branch that creates `MIMEText(body, "plain")` directly:
  ```python
  if body_html or attachments:
      msg = MIMEMultipart("mixed")
      if body_html:
          alt = MIMEMultipart("alternative")
          alt.attach(MIMEText(body, "plain"))
          alt.attach(MIMEText(body_html, "html"))
          msg.attach(alt)
      # ... attachment handling ...
  else:
      msg = MIMEText(body, "plain")
  msg["To"] = to
  msg["Subject"] = subject
  ```
  The same pattern applies to `send_email()` (SMTP) — check that code path too. After fixing, verify by triggering a plain-text email to a test lead. The action should complete on the first retry (no retries needed).
- **Result-checking in _execute_action: DO NOT ignore send results** — May 2026. The original `_execute_action()` called `wa.send_message_sync()` and `send_via_gmail_api()` WITHOUT checking their return values. Both returned error info (WhatsApp returns `{"error": "..."}`, Gmail returns `(bool, msg)`), but the code ignored them and always returned `True`. This meant actions marked `completed` even when WhatsApp was disconnected or Gmail OAuth expired. The scheduler's retry logic never kicked in. Fix: check results after every send call:
  ```python
  # WhatsApp
  result = wa.send_message_sync(lead.phone, message_text)
  if isinstance(result, dict) and result.get("error"):
      action.last_error = result["error"]
      logger.warning(f"WhatsApp send failed for {lead.name}: {result['error']}")
      return False  # ← triggers retry logic

  # Email
  success, err_msg = send_via_gmail_api(tokens, lead.email, subject, body)
  if not success:
      action.last_error = f"Email send failed: {err_msg}"
      logger.warning(f"Email send failed for {lead.name}: {err_msg}")
      return False  # ← triggers retry logic
  ```
  Apply this pattern to ALL code paths in `_execute_action()` (both the interpolated-payload path and the legacy-format path). There are 4 places that call `wa.send_message_sync()` and 2 that call `send_via_gmail_api()` — audit all of them.

- **Confirmation dialogs for destructive cadence actions** — Restart Outbound and Pause Outbound buttons need `confirm()` dialogs before proceeding. Without them, a single misclick cancels all pending activities for a lead:
  ```javascript
  // Restart
  if (!confirm('Are you sure? This will restart the outbound campaign for this lead — it will cancel all existing pending activities (emails, WhatsApp, calls) and reschedule the full sequence from scratch.')) return;

  // Pause
  if (!confirm('Are you sure? This will pause the outbound campaign for this lead — all pending activities (emails, WhatsApp, calls) will be cancelled. You can use "Restart Outbound" to resume later.')) return;
  ```

- **Trigger buttons in lead header** — Both buttons always visible in lead header next to Start AI Chat. **▶ Restart Outbound** (blue outline) calls trigger endpoint. **⏸ Pause Outbound** (red outline) calls pause endpoint, disabled when no pending actions. State determined by `var hasPending = l.scheduled_actions && l.scheduled_actions.length > 0`. Both call `showLeadDetail()` on completion to refresh. See `ara-cadence-logic` skill for full implementation details (confirmation dialogs, CSS, button naming history).

- **Email MIME attachment bug: `MIMEText.attach()` on non-multipart** — May 2026. `send_via_gmail_api()` in `email_utils.py` created `MIMEText(body, "plain")` for plain-text emails (no body_html), then called `.attach(MIMEText(...))` on it. `MIMEText` is a leaf MIME object, not a container — it has no `attach()` method. This raised: `"Cannot attach additional subparts to non-multipart/*"`. Fix: only create `MIMEMultipart` when `body_html` is provided. For plain-text emails, use `MIMEText(body, "plain")` directly without `attach()`:
  ```python
  if body_html:
      msg = MIMEMultipart("alternative")
      msg["To"] = to
      msg["Subject"] = subject
      msg.attach(MIMEText(body, "plain"))
      msg.attach(MIMEText(body_html, "html"))
  else:
      msg = MIMEText(body, "plain")
      msg["To"] = to
      msg["Subject"] = subject
  ```
  Same fix needed in both `send_via_gmail_api()` (Gmail) and `send_email()` (SMTP) in `email_utils.py`.
- **EMail path missing stage advancement in `_execute_action` (detected June 2026)** — The WhatsApp branch at line ~7093 has `if lead.stage == "new": lead.stage = "reached_out"`, but the **email branch** at line ~7110+ has NO equivalent code. When a cadence starts with email steps, the lead stays at `new` even after the email is sent. The pipeline context correctly shows `new`, but this creates a window where the system behaves inconsistently: the lead has been contacted (email sent) yet is still listed as untouched. Only a later WhatsApp step would advance the stage. **Fix:** Add the same stage advancement to the email branch:
  ```python
  if lead.stage == "new":
      lead.stage = "reached_out"
      lead.updated_at = utcnow()
      _sync_deal_stage_from_lead(lead.id)
  ```
  Apply after the email send succeeds (line ~7120, inside the `if tokens:` success path, after `send_via_gmail_api` returns True). Do NOT advance if the email failed — the retry path will trigger the advancement on the next attempt.

- **`create_action` notification uses description as message body (fixed June 2026)** — The dashboard `create_action` endpoint (line 2861) used `action.description` as the WhatsApp notification message: `notif_msg = action.description if action.description else f\"Reminder: {action.title}\"`. When descriptions contain raw notes (e.g., \"Win is shut off immediately with the sales use case in a non-integrated manner\"), the WhatsApp notification is incomprehensible jargon out of context. Fix: always use the title — `notif_msg = f\"Reminder: {action.title}\"`. Descriptions are internal notes, never user-facing notification text. The agent tools (`create_action_item`, `set_reminder`) were already correct — this bug was only in the dashboard endpoint.\n\n- **Action items without reminders (ScheduledAction missing) — backfill pattern** — Actions created before June 2026 through agent tools (`channel='call'`, `action_type='manual'`) did NOT get ScheduledActions. The `create_action` endpoint added ScheduledAction creation later, but existing items were never backfilled. Find with: `SELECT id, title FROM action_items WHERE due_at IS NOT NULL AND scheduled_action_id IS NULL AND execution_state IN ('pending','approved')`. Backfill with raw SQLite (not SQLAlchemy, avoids ORM session issues): insert into `scheduled_actions` with `scheduled_at = due_dt if future else now()`, `action_type='whatsapp_to_owner'`, `channel='whatsapp'`, and `payload` containing the message and action_item_id. Then update `action_items.scheduled_action_id`. Verify with a count query after backfill — all pending due-dated actions should have non-null `scheduled_action_id`.\n\n- **WhatsApp phone guard missing in `_execute_action` legacy path (detected June 2026)** — The legacy WhatsApp send path in `_execute_action` calls `wa.send_message_sync(lead.phone, message)` without checking if `lead.phone` is None/empty. When a lead has no phone number, this POSTs `{phone: null, text: "..."}` to the sidecar, which crashes on `null.replace(/\D/g, '')` with a TypeError. The scheduler retries 3 times (60s → 300s → 900s) then marks permanently failed. Unlike the email path which gracefully skips when `lead.email` is missing (returns True), WhatsApp has no guard. Fix: add the same pattern as email:
  ```python
  if not lead.phone or not lead.phone.strip():
      logger.warning(f"Lead {lead.name} has no phone, skipping WhatsApp send")
      return True
  ```
  Apply in BOTH the LLM-generated format path AND the legacy format path. There are two places calling `wa.send_message_sync(lead.phone, ...)` — fix both.

- **PATCH `approved` branch overrides `scheduled_at` with `utcnow()` (detected June 23, 2026)** — The `update_action` PATCH endpoint has an `execution_state == "approved"` branch that sets `sa.scheduled_at = utcnow()` to fire immediately. This OVERRIDES the correct `due_at` time stored on the ScheduledAction. When Greg approves an action with a future due_at (e.g., 11:30 AM), the SA fires immediately instead of at the due time. Result: \"Close Commercials (Sai Bharat)\" reminder fired at 6:00 AM instead of 11:30 AM. Fix needed: when approving an action with future due_at, preserve original `scheduled_at` from `action.due_at`, not `utcnow()`.\n\n### IST/UTC Conversion — Source of Truth (June 23, 2026)

**THE RULE:** All IST↔UTC conversions use exactly three functions defined in `app/config.py`. No ad-hoc arithmetic anywhere in the codebase.

```python
# app/config.py — the ONLY place IST↔UTC math lives
IST_OFFSET = _IST_TD(hours=5, minutes=30)  # 5h 30m

def ist_to_utc(dt):
    """Convert IST-naive datetime to UTC-naive. Subtracts 5:30. None-safe."""
    if dt is None:
        return None
    return dt - IST_OFFSET

def utc_to_ist(dt):
    """Convert UTC-naive datetime to IST-naive. Adds 5:30. None-safe."""
    if dt is None:
        return None
    return dt + IST_OFFSET

def parse_due_at(value):
    """Parse a due_at string. If date-only (no 'T'), defaults time to 18:00.
    Converts IST (user input) to UTC for storage. Returns None if empty.
    
    Handles the 'date-only skip' bug: previously create_action_item tool
    only converted when len(due_at_str) > 10, silently leaving date-only
    strings in IST instead of UTC."""
    if not value:
        return None
    if isinstance(value, str) and 'T' not in value:
        value += 'T18:00:00'
    dt = datetime.fromisoformat(value)
    return ist_to_utc(dt)
```

**Before (6+ scattered patterns):**
```python
due_at = due_at - timedelta(hours=5, minutes=30)  # create_action
due = due - IST_OFFSET                              # create_action_item
if len(due_at_str) > 10: due = due - IST_OFFSET     # date-only SKIPPED (BUG)
_due = _due - IST_OFFSET                            # agent tool
(c.created_at + IST_OFFSET).strftime(...)           # display conversion
```

**After (one source):**
```python
due_at = ist_to_utc(due_at)                         # create_action
due = parse_due_at(due_at_str)                      # create_action_item (handles date-only)
_due = ist_to_utc(_due)                             # agent tool
utc_to_ist(c.created_at).strftime(...)              # display conversion
```

**Import:** `from app.config import ist_to_utc, utc_to_ist, parse_due_at`

**Audit query:** `grep -c 'IST_OFFSET\|timedelta(hours=5, minutes=30)' server.py` — should return 0 (comment only). As of June 23, 2026: 1 (comment line).

**Pre-existing pitfalls that were fixed during consolidation:**
- `create_action_item` tool skipped IST→UTC for date-only strings (`len <= 10` guard) — fixed by using `parse_due_at()`
- `_parse_ava_due_at()` and `_format_utc_as_ist()` used `IST_OFFSET` directly — replaced with `ist_to_utc()`/`utc_to_ist()`
- 20 total ad-hoc conversion sites replaced across server.py

- **Unknown batch SA creation at 00:30 UTC — 9 ScheduledActions fire simultaneously (detected June 23, 2026)** — On June 23 at exactly 00:30:18 UTC (6:00 AM IST), 9 ScheduledActions were batch-created for action_items dating back to June 18. For 6 actions with past due_dates, `scheduled_at` was set to `utcnow()` (firing immediately at 6 AM). For 3 future actions, `scheduled_at = due_at` (correct). The batch creator is unknown — no matching cron, no batch function found in server.py. All 9 share the identical `created_at` timestamp down to the millisecond, suggesting a single synchronous loop. **Diagnosis query**: `SELECT * FROM scheduled_actions WHERE created_at = '2026-06-23 00:30:18.270981'`. **Mitigation**: add quiet-hours gate (10 PM-7 AM IST) in scheduler to suppress firing of batch-created SAs created during sleeping hours. Same pattern as `_check_action_notifications` midnight guard.

- **PATCH `execution_state=="approved"` branch overrides `scheduled_at` with `utcnow()` in `update_action` (detected June 23, 2026)** — When an action is approved via the PATCH endpoint, the code sets `sa.scheduled_at = utcnow()` to fire immediately. This OVERRIDES the correct `due_at`-based `scheduled_at`. Result: reminders fire at approval time (often 6 AM from batch processes) instead of the intended due time. Root cause: the `update_action` PATCH endpoint's approved branch at server.py ~L2975 unconditionally resets `scheduled_at` to `utcnow()`. Fix: only reset to `utcnow()` when no future `due_at` exists; otherwise preserve the `due_at`-based timing. See the `create_action` ScheduledAction sync section (v48 Build 1) for the fix pattern.

- **set_reminder / create_action_item notification gap with `due_at` but never created linked ScheduledActions. No notification was delivered. Root cause: only the `create_action` API endpoint (UI path) created ScheduledActions, gated on `due_type=="hard"` AND `channel=="whatsapp"`. The LLM doesn't set either field. Fix: both tools now create `ScheduledAction(action_type="whatsapp_to_owner", channel="whatsapp")` linked to the ActionItem whenever `due_at` or `delay_minutes` is provided. No gate on `due_type`. Production evidence: Dinesh Nagar ActionItem `31fab7b1` (due 9:00 AM IST, June 15) — `channel=none`, `scheduled_action_id=None`, no notification sent.

- **_next_working_time anchor-point reset (fixed June 2026)** — When `_next_working_time` received a time past 18:00 IST, it reset to exactly 9:00 AM the next day, zeroing out the intra-hour offset. With 1-hour interval repeats, all repeats that fell after 18:00 collapsed to 9:00 AM the next day — 12 email actions all firing at the exact same second. Fix: calculate a `past_close` timedelta (minutes/seconds past 18:00) and add it to next day's 9:00 start. E.g., 19:26 → 10:26 next day, not 9:00. Also add a safety re-check in case the offset wraps past 18:00 again. The `cache.clear()` pattern is fine here — this function is pure computation, no side effects.

- **Frontend fetchFromServer() skipped steps (fixed June 2026)** — The cadence builder's `fetchFromServer()` function only merged `promptParts` and `systemPrompt` from the published server config. Steps (channel + timing: delay, repeat_count, interval_hours) were NEVER loaded from the server. They came exclusively from `DEFAULT_TEMPLATES` in the JS or from localStorage. This meant that when Greg set "WhatsApp 8x every 1h" and published, the server saved correctly — but a page reload restored the DEFAULT_TEMPLATES timing. Fix (in `cadence_template.py`): (1) removed the `if promptParts empty` gate so `fetchFromServer()` always merges, (2) added merge for `steps`, `brandVoice`, `conditions`, `stopConditions`, `objective` from the server config, and (3) added `renderSteps()` call after merge so the DOM reflects the server's timing values immediately.

## Reference Files
- `references/implementation-qa-2026-05-26.md` — Raw Q&A transcript with Greg's design decisions (disqualification, meeting booking, human notification, etc.)
- `references/known-limitations.md` — Current system gaps and resolved limitations
- `references/lead-stage-tracing.md` — Methodology for tracing lead stage discrepancies between pipeline context and get_lead_detail. Covers scheduler race conditions, email/WhatsApp stage advancement gaps, and cron rescheduling timing.
- `references/debugging-failed-actions.md` — End-to-end debugging chain for failed scheduled actions
- `references/35-message-firehose.md` — Full incident report: 35 outbound messages to one lead in 5 minutes (June 15, 2026). Covers DB queries for failed actions, the failure chain trace, common failure patterns (lead.industry AttributeError, method name mismatches, arg count issues), the proactive alerting gap (LearningNotification created but never pushed to Greg), and Gmail integration status checks.
