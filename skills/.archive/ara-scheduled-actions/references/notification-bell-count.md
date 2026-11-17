# Notification Bell Count Logic (June 2026)

## Overview
The dashboard bell icon must show only actionable, unresolved items. Three layers of filtering applied to the `LearningNotification` query.

## Filter Layers (applied in order)

### Layer 1: Time-based stale exclusion
`action_failed` notifications older than 24 hours are excluded. These accumulate when the sidecar/Gmail was disconnected and all scheduled actions fail simultaneously.

```python
query = query.filter(
    ~((LearningNotification.notif_type == 'action_failed') &
      (LearningNotification.created_at < (utcnow() - timedelta(hours=24))))
)
```

### Layer 2: Ref-status cross-reference
Notifications that link to a `scheduled_action` ref must check whether the underlying action is still relevant. If the action is completed or cancelled, the notification is stale and excluded.

```python
if n.ref_type == "scheduled_action" and n.ref_id:
    sa = db.query(ScheduledAction).filter(ScheduledAction.id == n.ref_id).first()
    if sa and sa.status in ("completed", "cancelled"):
        continue  # exclude
```

### Layer 3: Actionable types only
Informational notification types (`synthesis_ready`, `meeting_booked`) should not trigger the bell. Only types requiring human action.

```python
actionable_types = {"escalation", "action_failed", "action_item", "call_reminder"}
if n.notif_type not in actionable_types:
    continue  # skip info-only
```

## Architecture
```python
# list_notifications() endpoint (server.py ~line 6059)
notifs = query.order_by(...).all()
filtered = []
for n in notifs:
    if n.ref_type == "scheduled_action" and n.ref_id:
        sa = db.query(ScheduledAction).filter(...).first()
        if sa and sa.status in ("completed", "cancelled"):
            continue
    if n.notif_type not in actionable_types:
        continue
    filtered.append(n)
return [{"id": n.id, ...} for n in filtered]
```

The bell icon count comes from `notifs.length` in the frontend (dashboard.js line ~1668, the unfiltered call to `/api/learning/notifications?acknowledged=false`).

## Pitfalls
- **Both filter calls in the frontend must be consistent.** The bell count comes from the UNFILTERED call (`?acknowledged=false` alone) at line 1512. The notification panel uses a TYPE-FILTERED call at line 2021. Both go through the same backend function, so the backend-level filters apply equally.
- **`action_failed` is in the actionable set** — recent failures DO need attention. Only stale ones (>24h) are excluded.
- **`synthesis_ready` is NOT actionable** — it's informational. The weekly synthesis is a report, not a task. It should not count toward the bell.
- **Do not use the stats endpoint for the bell count.** Stats returns `unread_notifications` which may use different filters. The bell count comes from the notification list endpoint directly.
- **Post-filtering, not query filtering.** The ref-status check requires a cross-table lookup that can't be done in a single SQL query efficiently. Fetch all matching notifications and post-filter.
