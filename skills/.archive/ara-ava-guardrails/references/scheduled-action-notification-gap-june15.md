# ScheduledAction Notification Gap — Two-Path Fix (June 15, 2026)

## The Bug

When the LLM calls `set_reminder` or `create_action_item` with a `due_at`, the tool creates an ActionItem but NEVER creates a `ScheduledAction`. The scheduler has nothing to deliver → no WhatsApp notification fires at the due time.

**Evidence:** Dinesh Nagar ActionItem `31fab7b1` (due 9:00 AM June 15) had `channel=none`, `scheduled_action_id=None`, `due_type=soft`. No notification was delivered.

## Root Cause

Two separate code paths both missed ScheduledAction creation:

### Path 1: LLM tool-call path (`execute_tool`)
`set_reminder` (line 4300) and `create_action_item` (line 4321) in `execute_tool()` created ActionItems but never called `ScheduledAction(...)`. Only the `create_action` API endpoint (line 2561, UI-only) created ScheduledActions, and only when `due_type=="hard"` AND `channel in ("whatsapp", "email")`.

### Path 2: Dashboard UI path (`POST /api/actions`)
The form defaults `channel="none"` and `due_type="soft"`. The ScheduledAction creation gate needed BOTH `due_type=="hard"` AND `channel in ("whatsapp", "email")` — and `channel="none"` failed the second condition. UI-created actions NEVER had notifications.

## The Fix

### Path 1 (`set_reminder` / `create_action_item`):
After creating the ActionItem, if `due_at` or `delay_minutes` is present:
1. Create `ScheduledAction(action_type="whatsapp_to_owner", scheduled_at=due_at, payload={"message": "⏰ **Reminder:** {title} ({lead_name})"})`
2. Set `action.scheduled_action_id = sa.id`
3. Set `action.channel = "whatsapp"`, `action.due_type = "hard"`, `action.execution_state = "fired"`

### Path 2 (`POST /api/actions`):
Changed from "create only when due_type==hard AND channel in (whatsapp, email)" to "create ALWAYS when due_at is set":
```python
if due_at:
    notif_msg = action.description if action.description else f"⏰ **Reminder:** {action.title}"
    lead_name = ""
    if action.ref_id:
        lead = db.query(Lead).filter(Lead.id == action.ref_id).first()
        if lead: lead_name = f" ({lead.name})"
    sa = ScheduledAction(
        action_type="whatsapp_to_owner",
        scheduled_at=due_at,
        payload={"message": notif_msg + lead_name}
    )
```

Also made `ref_id` optional in the POST endpoint (was required → prevented system-level actions).

### Default channel in form:
WhatsApp now pre-selected when form opens from lead detail page (`isLead ? ' selected' : ''`).

## Notification Format

All WhatsApp notifications from Ava to Greg use the same `✨ *Ava :*` header as coaching replies:

```
✨ *Ava :*

⏰ **Reminder:** Call Him (Prashant Rai)
```

The bare `"Ava: "` prefix is never used. Labels ("Reminder", "Action") are bold with `**label:**` markdown. This was a user correction on June 15 — Greg explicitly asked for the Ava coaching format on notifications.

## Verification

After the fix, any action created with a `due_at` (from UI or voice note) will have:
- `ActionItem.scheduled_action_id` → points to the ScheduledAction
- `ScheduledAction.status = "pending"`, `action_type = "whatsapp_to_owner"`
- Scheduler picks it up within 30 seconds of the due time
- WhatsApp delivers: `✨ *Ava :*\n\n⏰ **Reminder:** {Title} ({Lead Name})`
