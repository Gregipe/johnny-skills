# Notification Ref-Tracing: Debugging Stale Counts

When a notification badge/count shows a number that "feels wrong" — higher than the user expects, or includes items that should be resolved — the problem is almost always that notifications are being counted without checking whether their underlying reference is still active.

## Methodology

### Step 1: Break down the count by type

Query the raw notification records to see which types are contributing:

```sql
SELECT notif_type, COUNT(*) 
FROM learning_notifications 
WHERE acknowledged = false AND tenant_id = '...'
GROUP BY notif_type;
```

### Step 2: For each type, check the ref status

Types that reference other records (scheduled actions, action items) need cross-referencing:

| notif_type | ref_type | What to check |
|-----------|----------|---------------|
| `action_failed` | `scheduled_action` | Is the ScheduledAction still in failed state? Or was it superseded? |
| `action_scheduled` | `scheduled_action` | Is the ScheduledAction still `pending`/`firing` — or is it already `completed`/`cancelled`? |
| `synthesis_ready` | `synthesis` | Pure info — never actionable. Should not count toward "needs attention" badge. |
| `escalation` | (none) | Standalone — always actionable. |

### Step 3: Apply filters in priority order

1. **Time filter**: Stale `action_failed` older than 24h are noise — exclude them unconditionally
2. **Ref status filter**: For `action_scheduled` and `action_failed`, check if the referenced ScheduledAction's status is still active (pending/firing). If completed/cancelled, the notification is orphaned.
3. **Type filter**: Informational types (`synthesis_ready`) should not count toward an "action needed" badge. Only actionable types (escalation, action_failed, call_reminder, action_item) should increment the bell.

### Step 4: Apply to both endpoints

A common bug: fixing the display count but not the list endpoint, or vice versa. Apply the same filters to:

- **List endpoint** (returning notification objects) — affects what the user sees in the panel
- **Stats/count endpoint** (returning unread_notifications) — affects badge numbers
- **Frontend count** — the dashboard may compute counts from `notifs.length` rather than from the stats endpoint

## Design Principle

Greg's rule: "The bell should only show items that are **new AND open** — requiring action, not just informational."

Translation:
- **New** = unacknowledged (not yet seen)
- **Open** = still actionable (the underlying work hasn't been completed/resolved)
- Items that are informational only (synthesis ready, generic notices) should never count

## One-shot Fix Pattern

```python
# Step 1: Get all unacknowledged notifications (with stale time filter)
notifs = query.filter(
    ~((LearningNotification.notif_type == "action_failed") & 
      (LearningNotification.created_at < (utcnow() - timedelta(hours=24))))
).all()

# Step 2: Filter by ref status and type
actionable_types = {"escalation", "action_failed", "action_item", "call_reminder"}
filtered = []
for n in notifs:
    # Skip if ref is a completed/cancelled scheduled action
    if n.ref_type == "scheduled_action" and n.ref_id:
        sa = db.query(ScheduledAction).filter(ScheduledAction.id == n.ref_id).first()
        if sa and sa.status in ("completed", "cancelled"):
            continue
    # Skip info-only types
    if n.notif_type not in actionable_types:
        continue
    filtered.append(n)

count = len(filtered)
```
