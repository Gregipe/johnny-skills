# Voice Stage Auto-Cancel & Cron Timing — Fix Reference

## Voice Stage Auto-Cancel Bug

**Symptom:** Brain dump creates two pending actions. User says "confirm." Only the LAST action gets created — the first one silently disappears. When staging action 2, action 1's `execution_state` gets set to `cancelled`.

**Root cause:** The `/api/voice/stage` endpoint in `server.py` (~line 13011) had a block that cancelled ALL existing voice-pending actions before creating a new one:

```python
# Cancel any existing voice pending for this tenant (only one at a time)
_existing = db.query(ActionItem).filter(
    ActionItem.tenant_id == tenant_id,
    ActionItem.execution_state == "awaiting_approval",
    ActionItem.action_type == _VOICE_PENDING_CONFIRM_ACTION_TYPE,
).all()
for _row in _existing:
    _row.execution_state = "cancelled"
    _row.status = "resolved"
    _row.outcome_state = "cancelled"
```

**Fix:** Remove the cancel-previous block entirely. Multiple voice-pending actions coexist. The LLM confirms each via individual `voice_confirm` calls with their specific `pending_id`. TTL-based cleanup handles stale pendings.

**Verification:**
```bash
# Stage two actions — both should get pending_ids
curl -X POST localhost:8766/api/voice/stage \
  -H "Content-Type: application/json" \
  -d '{"tool_calls":[{"tool":"set_reminder","args":{"title":"Action 1","due_at":"2026-07-14T09:00:00"}}],"secret":"...","tenant_id":"3e736242"}'
# Returns: {"ok":true,"pending_id":"da31ae4b",...}

curl -X POST localhost:8766/api/voice/stage \
  -H "Content-Type: application/json" \
  -d '{"tool_calls":[{"tool":"set_reminder","args":{"title":"Action 2","due_at":"2026-07-15T09:00:00"}}],"secret":"...","tenant_id":"3e736242"}'
# Returns: {"ok":true,"pending_id":"307b4e62",...}

# Confirm both — both should execute
curl -X POST localhost:8766/api/voice/confirm \
  -H "Content-Type: application/json" \
  -d '{"pending_id":"da31ae4b","cancel":false,"secret":"...","tenant_id":"3e736242"}'
curl -X POST localhost:8766/api/voice/confirm \
  -H "Content-Type: application/json" \
  -d '{"pending_id":"307b4e62","cancel":false,"secret":"...","tenant_id":"3e736242"}'
```

---

## Cron Job WhatsApp — Wrong Schedule Fix

**Symptom:** WhatsApp brief delivered at 1:32 AM and 3:21 AM IST. User receives notifications while sleeping.

**Root cause:** Cron job `daily-whatsapp-brief` (job_id: `00fbbc53fd87`) had schedule `30 1 * * *` (1:30 AM IST). No time-window guard in prompt.

**Fix — two layers:**
1. **Schedule:** Change to a reasonable morning time: `30 7 * * *` (7:30 AM IST)
2. **Prompt guard:** Add at top of prompt: `IMPORTANT: Only proceed if current time is between 7:00 AM and 10:00 PM IST. If outside this window, do nothing — do not send any messages.`

**Memory rule:** Night-time (10 PM to 7 AM IST) delivery is never acceptable. Communication window is 7 AM to 10 PM IST.

---

## User Preference: Sharp Brain Dump Summaries

Greg wants brain dump summaries to be SHARP — only include what was actually discussed. Skip empty section headers like "UPDATES — None requested yet." Only show categories with actual content.
