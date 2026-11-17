# Notification Tracing & Backfill Pattern

## Confusing WhatsApp Notification

When Greg gets a confusing notification like "Win is shut off immediately with the sales use case in a non-integrated manner. (Vinay Bhoj)":

1. **Find the scheduled action**: `SELECT * FROM scheduled_actions WHERE payload LIKE '%keyword%'`
2. **Extract action_item_id** from payload JSON
3. **Query action_items**: title vs description — check if description was used as notification body
4. **Find the lead**: `SELECT * FROM leads WHERE id = ref_id`
5. **Check for conversations/learnings**: `SELECT * FROM conversations WHERE lead_id = ?`

**Bug**: `create_action` endpoint line 2861 used `action.description` as notification body when description exists: `notif_msg = action.description if action.description else f"Reminder: {action.title}"`. Fix: always use title — descriptions are internal notes.

## Reminders Never Fired

When Greg expects reminders at specific times but they don't arrive:

1. **Check for missing ScheduledActions**: `SELECT COUNT(*) FROM action_items WHERE due_at IS NOT NULL AND scheduled_action_id IS NULL AND execution_state IN ('pending','approved')`
2. **Common cause**: Actions created before ScheduledAction creation logic was added to `create_action` (pre June 18, 2026) or created through agent tools (`channel='call'`, `action_type='manual'`)
3. **Backfill**:
```sql
INSERT INTO scheduled_actions (id, tenant_id, lead_id, action_type, status, scheduled_at, channel, payload, created_at)
VALUES (?, ?, ?, 'whatsapp_to_owner', 'pending', ?, 'whatsapp', ?, ?)
```
Where `scheduled_at = due_dt if due_dt > now else now()`.
4. **Link**: `UPDATE action_items SET scheduled_action_id = ? WHERE id = ?`
5. **Verify**: `SELECT COUNT(*) FROM action_items WHERE scheduled_action_id IS NULL AND due_at IS NOT NULL` → should be 0

## Midnight Notification Spam

Greg gets overdue reminders at 00:00 IST because `_check_action_notifications()` runs every 30s and the dedup window (`today_start`) resets at midnight IST. All past-due items fire simultaneously.

**Fix**: Quiet-hours gate at top of `_check_action_notifications()`:
```python
hour = ist_now.hour
if hour < 7 or hour >= 22:
    return  # silently skip 10PM-7AM IST
```

## Lead Actions Tab Empty

When lead detail page shows "0 actions" despite having items:

**Check**: Frontend fetch URL vs backend route. The dashboard called `/api/actions/{leadId}` but the backend route is `/api/leads/{leadId}/actions`. A single missing `/leads/` segment silently misroutes.

**Verify**: `curl http://localhost:8766/api/leads/{leadId}/actions` — should return actions. Then grep `dashboard.js` for the fetch URL to confirm match.
