# Debugging Failed Scheduled Actions — End-to-End

## Symptom Collection

When Greg reports that something didn't fire or "Ava is Thinking" appeared without a response:

1. **Get timestamps** — exact times he saw the issue (e.g. 9:35, 9:39, 9:40, 9:48 AM)
2. **Check the scheduler logs** — `journalctl -u ara-server --since "2026-06-13 09:30" --until "2026-06-13 09:50"` (narrow window to the minute)
3. **Check error.log** — `tail -20 /opt/ara/logs/error.log`
4. **Check `/api/logs` ring buffer** (in-memory last 200 entries)
5. **Query the DB directly** for failed actions (see below)

## DB Queries for Failed Actions

```python
from server import init_db, TENANT_ID
from database import ScheduledAction, LearningNotification, Lead
db = init_db()

# 1. All permanently failed actions
failed = db.query(ScheduledAction).filter(
    ScheduledAction.tenant_id == TENANT_ID,
    ScheduledAction.status == "failed",
).all()
print(f"Failed actions ({len(failed)}):")
for a in failed:
    l = db.query(Lead).filter(Lead.id == a.lead_id).first()
    print(f"  {a.action_type} for {l.name if l else '?'}: {a.last_error}")

# 2. Recent action_failed LearningNotifications (bell icon, not pushed)
notifs = db.query(LearningNotification).filter(
    LearningNotification.tenant_id == TENANT_ID,
    LearningNotification.notif_type == "action_failed",
).order_by(LearningNotification.created_at.desc()).limit(5).all()
print(f"Action failed notifications ({len(notifs)}):")
for n in notifs:
    print(f"  {n.title}: {n.message[:100]}")
```

## The Failure Chain

When a scheduled action fails, trace through this path:

```
User reports failure
  ↓
_runs every 30s → _run_scheduler picks up due action
  ↓
Sets status = "firing", calls _execute_action(action, db)
  ↓
Checks payload._format → "llm" path (generates message) or legacy path
  ↓
_generate_step_message(step, lead, template, ...) → uses lead data
  ↓
channel == "whatsapp" | "email" | "call" → dispatches to send function
  ↓
On success: status="completed" (or rescheduled for cron)
On failure: retry_count++ → exponential backoff → max retries → permanent failure
  ↓
Permanent failure → LearningNotification(notif_type="action_failed") created
  ↓
**STOP** — Notification is NEVER pushed to Greg (no _notify_owner call)
```

## Common Failure Patterns

| Error | Location | Fix |
|-------|----------|-----|
| `'Lead' object has no attribute 'industry'` | `app/services/cadence.py:254` — `lead.industry` referenced | Use `lead.product_interest or 'Not specified'` — Lead model has no `industry` column |
| `'WhatsAppManager' object has no attribute 'send'` | `_execute_action()` — wrong method name | Use `wa.send_message_sync()` not `wa.send()` |
| `send_via_gmail_api() missing 1 arg` | `_execute_action()` — wrong arg count | Pass `(tokens, to, subject, body)` — 4 args |
| Gmail UnboundLocalError on `msg` | `send_via_gmail_api()` — plain-text path | Add `else: msg = MIMEText(body, "plain")` |
| WhatsApp phone None crash | `_execute_action()` — no phone guard | Add `if not lead.phone: return True` before send |
| No Gmail tokens | Email send path | `action.last_error = "No Gmail OAuth tokens"` — check IntegrationConfig |
| Scheduled actions succeed but no push to Greg | Notification chain gap | `LearningNotification` created but `_notify_owner` never called → notification visible only via bell API |

## Proactive Alerting Gap

The system creates `LearningNotification(notif_type="action_failed")` for permanently failed actions, but:

1. `_notify_owner()` is **never called** for failed actions — it exists at line ~687 for WhatsApp/email alerts, but the scheduler doesn't use it
2. Pipeline context injection (`watchlist_context` at line ~4932) only reads `AvaWatchlist` table — not `LearningNotification`
3. The only way to see failed actions is via `GET /api/learning/notifications?types=action_failed` (bell icon API)
4. Andy actions with `ref_type="scheduled_action"` and `ref_id` are post-filtered: if the underlying `ScheduledAction` is now `completed` or `cancelled`, the notification is skipped

This means Greg won't know about a failure unless he happens to check the bell icon or ask directly.

## How to Check

```bash
# Quick check — how many failed actions
ssh root@46.224.132.99 'cd /opt/ara && /opt/ara/venv/bin/python3 -c "
from server import init_db, TENANT_ID
from database import ScheduledAction, LearningNotification, Lead
db = init_db()
failed = db.query(ScheduledAction).filter(
    ScheduledAction.tenant_id == TENANT_ID,
    ScheduledAction.status == \"failed\",
).all()
for a in failed:
    l = db.query(Lead).filter(Lead.id == a.lead_id).first()
    print(f\"  {a.action_type} for {l.name if l else \"?\"}: {a.last_error}\")
db.close()
"'

# Check a specific lead
ssh root@46.224.132.99 'cd /opt/ara && /opt/ara/venv/bin/python3 -c "
from server import init_db, TENANT_ID
from database import Lead
db = init_db()
l = db.query(Lead).filter(Lead.name == \"Gregory Ipe\", Lead.tenant_id == TENANT_ID).first()
if l: print(f\"Name: {l.name} | Stage: {l.stage} | Email: {l.email} | Phone: {l.phone}\")
db.close()
"'
```

## Gmail Integration Status

```python
from server import init_db, TENANT_ID
from database import IntegrationConfig
db = init_db()
cfg = db.query(IntegrationConfig).filter(
    IntegrationConfig.tenant_id == TENANT_ID,
    IntegrationConfig.integration_id == "email-gmail",
).first()
if cfg:
    print(f"Gmail: enabled={cfg.enabled}, has_config={bool(cfg.config)}")
```

## When the Scheduler Logs Are Empty

The scheduler writes to `logging.getLogger("scheduler")` which goes to the root logger. Root logger goes to:
1. stderr → should be captured by journald (but may be suppressed by Uvicorn log level)
2. In-memory ring buffer → accessible via `/api/logs`
3. ERROR+ → `/opt/ara/logs/error.log` (rotating file, 5MB)

If journalctl is empty for a time range, check `/api/logs` and the error log. Also check if the server was restarted since last restart (the ring buffer is in-memory and resets on restart).
