# Voice Auto-Reminders — Server-Side Scheduling

Date: 2026-07-10

## Problem

When Ava creates actions via voice, Greg expects two things:
1. An immediate WhatsApp summary of what was created
2. A WhatsApp reminder 2 hours before each action's due time

The LLM via system prompt could handle #1 (post-confirmation `send_whatsapp_to_owner` call), but #2 was unreliable — the LLM often forgot to schedule reminders alongside action creation.

## Solution: Server-Side Auto-Scheduling

Both behaviors are now server-enforced in the `voice_confirm` handler (`/opt/ara/server.py`):

### 1. Immediate Summary WhatsApp
After all tools execute successfully, the handler builds a summary message:
```
📋 Created via voice:
✅ Check in with Moksh Malji at 06:00 PM IST
✅ Chat on commercials with Devashish Sarin at 06:00 PM IST
```
This creates a `ScheduledAction` with `scheduled_at=now()`, so the WhatsApp sidecar delivers it immediately.

### 2. Two-Hour-Before Reminders
For every executed tool that is `create_action`, `create_action_item`, or `set_reminder` AND has a `due_at` or `delay_minutes`, the handler:

1. Resolves the lead from `lead_name` (if provided)
2. Calculates `reminder_time = due_at - 2 hours`
3. Creates a `ScheduledAction` with `action_type="whatsapp_to_owner"` at that time
4. If `reminder_time` is in the past, skips it (no point reminding for already-due items)

The message format:
```
⏰ Reminder: {title} ({lead_name})
```

## Code Location

`/opt/ara/server.py` → `voice_confirm()` handler, after `# Mark fired` section.

## LLM Responsibilities (Remaining)

The system prompt still instructs Ava to call `send_whatsapp_to_owner` after batch confirmation as a backup, but the server-side code handles the primary case. The remaining LLM responsibilities:

1. Pass `lead_name` to `set_reminder` so reminders link to leads
2. Pass `due_at` in ISO format for time-based actions
3. Don't create orphan reminders without lead context

## CRITICAL: Deploy via scp'd Scripts — Never inline python3 -c

The auto-reminder code was deployed via shell one-liner (`python3 -c "..."`)\nwith multi-level escaping. The nested quotes and escape sequences got corrupted\n— the code was syntactically valid but semantically broken (missing lead_id\nresolution, wrong condition checks). The code compiled but never actually ran.

**Rule:** When deploying Python changes to server.py that are more than a\ntrivial one-liner, write the patch as a standalone `.py` script, `scp` it to\nthe server, then run it. Never inline via `python3 -c` with shell escaping.\n\n## Backfill Script for Orphan Reminders\n\nWhen the auto-reminder system was broken, many actions were created without\nreminders. The backfill script at `/tmp/bf.py` (July 10) handles:\n- Querying all pending manual/set_reminder ActionItems with due_at\n- Checking for existing matching ScheduledActions (\u00b15 min window)\n- Deleting duplicate/wrong-time SAs\n- Creating correct 2-hour-before reminders with lead linkage\n- Updating `scheduled_action_id` FK on ActionItem\n\nThe pattern uses `ActionItem.payload.contains(title[:15])` to find orphan\nSAs, then filters by time proximity. Reminders in the past are skipped.\n\n## July 10 Audit — 7 Bugs Found and Fixed

A full code audit + live test against the database revealed the auto-reminder block
was **completely non-functional**. Two critical bugs prevented any reminders from being
created:

### Bug 1 — CRITICAL: Timezone-aware vs naive datetime comparison crash (line 13236)
`_remind_at > datetime.utcnow()` compares timezone-aware to naive → `TypeError`.
Swallowed by `except Exception: pass`. Fix: `_remind_at > datetime.now(timezone.utc)`.

### Bug 2 — CRITICAL: IST→UTC conversion skipped (lines 13223-13234)
LLM passes `due_at` as IST local string (e.g. `"2026-07-13T18:00:00"`). The
`create_action` handler runs `ist_to_utc()` (subtracts 5:30), but the auto-reminder
block parsed the raw string as UTC. Reminders fired 5h30m too late. Fix: call
`ist_to_utc(_due_dt)` before setting tzinfo.

### Bug 3 — MODERATE: Double-reminder for set_reminder/create_action_item
`set_reminder` and `create_action_item` handlers already create their own
ScheduledActions (at due time). The auto-reminder block creates a SECOND one
(2h before due). Only `create_action` needs auto-reminders. Fix: restrict to
`if _tn != "create_action": continue`.

### Bug 4 — MODERATE: `datetime.utcnow()` deprecated in Python 3.14
Fix: `datetime.now(timezone.utc)` everywhere.

### Bug 5 — MODERATE: Lead resolution inconsistency
Auto-reminder used raw `ilike("%" + _alead + "%")` (first match by insertion order).
`create_action` handler uses `resolve_lead()` (exact → prefix → phonetic, raises
`AmbiguousLeadError` on multiple matches). Fix: use `resolve_lead()` in auto-reminder.

### Bug 6 — MINOR: Timezone-aware datetime stored in SQLite
`scheduled_at=_remind_at` (with tzinfo) creates inconsistency with naive UTC columns
used elsewhere. Fix: `scheduled_at=_remind_at.replace(tzinfo=None)`.

### Bug 7 — MINOR: Missing `_datetime` import
`_datetime.fromisoformat()` called without importing `_datetime`. Fix: add
`from datetime import datetime as _datetime` inside the try block.

**Live test after fix**: pending_id created → `POST /api/voice/confirm` → HTTP 200 →
ScheduledAction found with `scheduled_at = due_at - 2 hours` ✓

## Verification

Write verification script, scp to server, run:
```bash
cat > /tmp/verify_reminders.py << 'XEOF'
import sys; sys.path.insert(0, "/opt/ara")
import database; database.init_db()
db = database.SessionLocal()
from database import ScheduledAction, ActionItem
from datetime import datetime, timezone, timedelta
cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
sas = db.query(ScheduledAction).filter(
    ScheduledAction.action_type == "whatsapp_to_owner",
    ScheduledAction.created_at >= cutoff,
).order_by(ScheduledAction.created_at.desc()).limit(10).all()
for sa in sas:
    lead = sa.lead_id[:8] if sa.lead_id else "NONE"
    msg = sa.payload.get("message", "")[:80] if sa.payload else ""
    print(f"{sa.id[:8]} | lead={lead} | {sa.scheduled_at} | {msg}")
db.close()
XEOF
scp /tmp/verify_reminders.py root@46.224.132.99:/tmp/
ssh root@46.224.132.99 "/opt/ara/venv/bin/python /tmp/verify_reminders.py"
```
