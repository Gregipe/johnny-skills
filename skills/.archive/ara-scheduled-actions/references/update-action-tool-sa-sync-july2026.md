# update_action Tool Handler — ScheduledAction Sync Gap (July 12, 2026)

## Bug
The `update_action` tool handler (line 5438, called by Ava via voice/chat) updates `ActionItem.due_at` but does NOT sync the corresponding `ScheduledAction` reminder. Only the REST PATCH endpoint (`@app.patch("/api/actions/{action_id}")`, line 2996) syncs the reminder — but Ava never calls that endpoint.

## Result
When Greg updates an action's due date via Ava (voice or chat), `ActionItem.due_at` changes but `ScheduledAction.scheduled_at` stays at the old time. The 2-hour-before WhatsApp reminder fires at the wrong time.

## Root Cause
The tool handler and REST endpoint are independent code paths. The ScheduledAction sync logic was only added to the REST endpoint. When the voice agent calls `update_action` via the tool handler, the SA is never touched.

## Fix (bd3df0a)
Added ScheduledAction sync logic to the `update_action` tool handler in `server.py`, mirroring the PATCH endpoint:

```python
# After updating action.due_at in the tool handler:
if action.due_at and action.due_at > utcnow().replace(tzinfo=None):
    from database import ScheduledAction as _SA, Lead as _LdUpd
    _lead = db.query(_LdUpd).filter(_LdUpd.id == action.ref_id).first() if action.ref_id else None
    _sa = None
    if action.scheduled_action_id:
        _sa = db.query(_SA).filter(_SA.id == action.scheduled_action_id).first()
        if _sa:
            if action.due_at != _sa.scheduled_at:
                _sa.scheduled_at = action.due_at
                _sa.status = "pending"
        else:
            action.scheduled_action_id = None
    if not action.scheduled_action_id:
        _remind_at = action.due_at - timedelta(hours=2)
        now_utc = utcnow().replace(tzinfo=None)
        if _remind_at > now_utc:
            _sa = _SA(
                id=str(uuid.uuid4())[:8],
                tenant_id=tenant_id,
                lead_id=action.ref_id,
                action_type="whatsapp_to_owner",
                channel="whatsapp",
                scheduled_at=_remind_at,
                status="pending",
                payload={...}
            )
            db.add(_sa)
            action.scheduled_action_id = _sa.id
```

## Design Rule
**Any code path that modifies `ActionItem.due_at` MUST also sync the ScheduledAction.** The REST endpoint and tool handler are separate code paths that drift independently. Audit both when changing due_at logic.

## Notification Details
- Trigger: 2 hours before `due_at`
- Channel: WhatsApp only (`whatsapp_to_owner`)
- Dispatcher: `_run_scheduler()` background daemon, polls every 30s
