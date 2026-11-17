# Reducing Noise in Status Counters (Bell Icon, Badges, Notification Counts)

A repeatable pattern for fixing status counters that show incorrect numbers because they count stale, resolved, or irrelevant entries alongside active ones.

## The Problem

A counter (bell icon badge, unread count, pending items) shows a number that doesn't match what the user actually needs to act on. The count includes:
- Stale entries (completed actions from days ago)
- Entries whose underlying ref is already resolved
- Purely informational entries that don't require action

## The Three-Layer Filter Pattern

Apply these three filters IN ORDER. Each addresses a different kind of noise.

### Layer 1: Time-Based Filter (Exclude Stale)

Purpose: Remove entries that are too old to be actionable but haven't been cleaned up.

```python
# Filter out action_failed older than 24 hours
from datetime import timedelta
query = query.filter(
    ~((LearningNotification.notif_type == "action_failed") & 
      (LearningNotification.created_at < (utcnow() - timedelta(hours=24))))
)
```

**When to apply:** Any counter where stale/failed entries accumulate over time without auto-cleanup. Common with action_failed, error, and warning notification types.

**Key decision: filter at DB query level vs post-filter?** If the filter is simple (by type + age), add it to the query to reduce data transfer. If it involves cross-table checks, post-filter after the main query.

### Layer 2: Cross-Reference Filter (Check Underlying Entity Status)

Purpose: A notification about an action is meaningless if the underlying action is already done.

```python
notifs = query.all()
filtered = []
for n in notifs:
    if n.ref_type == "scheduled_action" and n.ref_id:
        sa = db.query(ScheduledAction).filter(ScheduledAction.id == n.ref_id).first()
        if sa and sa.status in ("completed", "cancelled"):
            continue  # action is done — skip this notification
    filtered.append(n)
```

**When to apply:** Notifications have a `ref_type`/`ref_id` that points to another entity (scheduled action, action item, conversation). The notification isn't cleaned up when the underlying entity changes state.

**Pattern for each ref type:**

| ref_type | Underlying entity | Check field(s) | Skip condition |
|----------|------------------|----------------|----------------|
| `scheduled_action` | ScheduledAction | `status` | `completed`, `cancelled` |
| `action_item` | ActionItem | `status` | `resolved`, `dismissed` |
| `synthesis` | No cross-check needed | — | Always valid (synthesis periods don't expire) |

### Layer 3: Actionability Filter (Exclude Informational Types)

Purpose: Not every notification type represents something the user needs to act on. Info-only types (summaries, reports) should not inflate action counters.

```python
actionable_types = {"escalation", "action_failed", "action_item", "call_reminder"}
filtered = [n for n in filtered if n.notif_type in actionable_types]
```

**When to apply:** The counter is meant to show "things requiring action" but includes purely informational notifications.

**Common info-only types to exclude:**
- `synthesis_ready` — "Weekly synthesis ready" — informational
- `internal_note` — Ava's self-notes — internal only
- Any notification type where the user doesn't need to *do* anything

## Debugging Protocol

When the user says the count is wrong:

1. **Check what's in the count** — query the raw data and group by type:
   ```sql
   SELECT notif_type, COUNT(*) FROM learning_notifications
   WHERE acknowledged = 0 AND tenant_id = '...'
   GROUP BY notif_type;
   ```

2. **Apply Layer 1** — add time filter for stale action_failed, re-check count

3. **Apply Layer 2** — for each notification with a ref_type/ref_id, check the underlying entity's status. Log which ones get excluded and why.

4. **Apply Layer 3** — decide which notification types are informational vs actionable

5. **Verify with the user** — after applying all three layers, the count should match what they expect to see

## Pitfalls

- **Don't apply Layer 3 too broadly** — an `escalation` notification IS actionable and should always be counted. Only exclude types that are definitively not action-oriented.
- **Layer 2 is expensive on large datasets** — each cross-reference is a separate DB query. For tables with hundreds of entries, batch the cross-refs first (e.g., collect all ref_ids, query them in one `IN(...)` statement, then build a lookup dict).
- **Don't filter at the wrong layer** — using a time filter (Layer 1) when you should be checking ref status (Layer 2) will either miss some or exclude too many. Apply all three layers sequentially.
- **The DB might have many unacknowledged rows that are all stale** — the API may show a small filtered count, but the raw DB count is still high. If the user checks the DB directly, they'll see the unfiltered number.
- **Notification list endpoint vs stats endpoint** — the bell icon may pull from a different endpoint than the notification panel. Always check which frontend call drives which visual element.
