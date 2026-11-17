# Scheduled Owner Messages (send_whatsapp_to_owner with delay_minutes)

## What Changed

Added `delay_minutes` support to `send_whatsapp_to_owner`. Before, Ava could only send instant WhatsApp messages to Greg. Now she can schedule them for later delivery.

## How It Works

### Tool Level (server.py, line ~3816)

The `send_whatsapp_to_owner` tool now accepts an optional `delay_minutes` parameter:

```python
message = args.get("message", "")
delay_minutes = int(args.get("delay_minutes", 0))
```

**Immediate send (delay_minutes=0 or omitted):** Same as before — `wa.send_message_sync(admin.phone, "Ava: " + message)` fires instantly.

**Scheduled send (delay_minutes > 0):** Creates a `ScheduledAction` in the DB with `action_type="whatsapp_to_owner"`, `lead_id=None`, and a scheduled time of `utcnow() + delay_minutes`. The scheduler picks it up and delivers via `wa.send_message_sync()` at the right time.

### Scheduler Level (server.py, line ~7618)

The legacy action executor now handles `action_type == "whatsapp_to_owner"`:

```python
elif action.action_type == "whatsapp_to_owner":
    message = payload.get("message", "")
    if message:
        admin = db.query(User).filter(
            User.tenant_id == action.tenant_id,
            User.role == "admin"
        ).first()
        if admin and admin.phone:
            result = wa.send_message_sync(admin.phone, "Ava: " + message)
```

This lives in the `_execute_action()` function's legacy format section, alongside the `whatsapp` (to lead), `email`, `call_reminder`, and `internal_note` handlers.

### Prompt Level

The tool schema description was updated to show the optional `delay_minutes`:

```
**send_whatsapp_to_owner** — Send WhatsApp to Greg (or schedule with delay_minutes). Args: {"message": "...", "delay_minutes": 30}
```

## Key Files

| File | What Changed |
|------|-------------|
| `server.py` line ~3816 | `send_whatsapp_to_owner` handler: added `delay_minutes` param + scheduling logic |
| `server.py` line ~7618 | `_execute_action()`: added `whatsapp_to_owner` handler |
| `server.py` line ~4994 | Tool schema: updated description with `delay_minutes` |

## Ava's Responses

| Query | Response |
|-------|----------|
| "Send me a WhatsApp now saying 'Call Dave'" | Sends instantly |
| "Send me a WhatsApp in 10 minutes saying 'Time for standup'" | Schedules, returns "📬 WhatsApp scheduled to you at [time] ([N] min from now). Preview: ..." |

## Pitfalls

- The `whatsapp_to_owner` action type has `lead_id=None` — the scheduler skips lead lookups and sends directly to the admin's phone
- Works even if the ARA server has restarted between scheduling and delivery (persisted in DB)
- The sidecar must be connected when the scheduled time fires — if it's disconnected, the send will fail and the action stays "pending" (no retry)
