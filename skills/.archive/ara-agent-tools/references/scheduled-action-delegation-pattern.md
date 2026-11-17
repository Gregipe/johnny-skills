# ScheduledAction Delegation Pattern

## Problem
Tool handlers that send emails or messages directly via API (Gmail, WhatsApp) need retry logic, error handling, and async delivery. Writing this inside every `execute_tool()` handler duplicates code and creates inconsistency.

## Solution
Instead of calling the send API directly, create a `ScheduledAction` with a 1-minute delay:

```python
scheduled_at = utcnow() + timedelta(minutes=1)
action = ScheduledAction(
    tenant_id=tenant_id,
    lead_id=lead.id,
    action_type="email",       # or "whatsapp"
    status="pending",
    scheduled_at=scheduled_at,
    payload={"subject": subject, "body": body},
    channel="email",
)
db.add(action)
db.commit()
```

## Benefits
- **Retries**: The existing scheduler daemon handles failures and retries
- **Consistency**: Same delivery path as cadence-triggered sends
- **Observability**: Shows in scheduled_actions table alongside other pending actions
- **No threading**: Tool handler returns instantly, delivery is async

## When to use
Use when the send can tolerate a 1-minute delay. For true instant delivery (user expects immediate feedback), call the send API directly in the handler.
