# Enhanced Lead Detail — Full Action History

## What Changed

`get_lead_detail` handler in `server.py` previously only showed `status == "pending"` actions:

```python
pending = db.query(ScheduledAction).filter(
    ScheduledAction.lead_id == lead.id,
    ScheduledAction.status == "pending",
).order_by(ScheduledAction.scheduled_at.asc()).all()
```

This made it impossible to see what happened with previous cadence attempts — failures, cancellations, completed sends were all invisible.

## Fix

Query all statuses, last 15, with status badges:

```python
all_actions = db.query(ScheduledAction).filter(
    ScheduledAction.lead_id == lead.id,
).order_by(ScheduledAction.scheduled_at.desc()).limit(15).all()

status_icon = {"pending": "⏳", "firing": "🔥", "completed": "✅", "failed": "❌", "cancelled": "🚫"}
action_lines = []
for a in all_actions:
    icon = status_icon.get(a.status, "•")
    ts = a.scheduled_at.strftime('%b %d %I:%M%p') if a.scheduled_at else '?'
    action_lines.append(f"  {icon} [{ts}] {a.status}: {a.action_type} via {a.channel}")
```

## Why It Matters

When a cadence email fails (e.g., `lead.industry` crash, missing Google API package, OAuth token expired), the lead detail now shows:

```
Recent actions:
  ❌ [Jun 13 02:38PM] failed: email via email
  ⏳ [Jun 13 03:38PM] pending: email via email
  ⏳ [Jun 13 04:38PM] pending: email via email
```

The user can immediately see that the first attempt failed and subsequent ones are queued — no need to dig through logs or ask "did it send?"
