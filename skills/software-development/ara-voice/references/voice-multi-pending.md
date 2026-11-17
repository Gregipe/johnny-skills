# Voice Multi-Pending Coexistence

## Problem

The `/api/voice/stage` endpoint originally cancelled ALL existing voice-pending ActionItems before creating a new one. When a brain dump staged 2+ actions, only the last one survived.

User flow:
- Brain dump identifies 3 actions
- LLM calls `create_action` for action 1 → stages → pending_id_1
- LLM calls `create_action` for action 2 → stages → **pending_id_1 cancelled**, pending_id_2 created
- LLM calls `create_action` for action 3 → stages → **pending_id_2 cancelled**, pending_id_3 created
- User says "confirm" → only action 3 exists → only action 3 is created
- User: "where are my other two actions?" ← discovered during QA

## Fix

Removed the eager cancellation block from `voice_stage()` in server.py:

```python
# OLD (cancelled all previous):
_existing = db.query(ActionItem).filter(
    ActionItem.tenant_id == tenant_id,
    ActionItem.execution_state == "awaiting_approval",
    ActionItem.action_type == _VOICE_PENDING_CONFIRM_ACTION_TYPE,
).all()
for _row in _existing:
    _row.execution_state = "cancelled"

# NEW (coexistence):
# Multiple voice-pending actions can coexist (brain dump may stage several)
# Cleanup of stale pendings is handled via TTL expiry, not eager cancellation
```

## User Flow After Fix

- Brain dump identifies 3 actions
- LLM calls `create_action` × 3 → all 3 survive (pending_id_1, pending_id_2, pending_id_3)
- User says "confirm" → LLM calls `voice_confirm(cancel=false, pending_id=<id>)` for each
- All 3 actions created

## Confirmation Protocol

The LLM must track multiple pending_ids and confirm each one separately. The system prompt for brain dump mode instructs:

```
When the user says "confirm", confirm ALL pending voice actions.
If there are multiple, confirm them one by one.
```

The LLM calls:
```
voice_confirm(cancel=false, pending_id=<id_1>)
voice_confirm(cancel=false, pending_id=<id_2>)
voice_confirm(cancel=false, pending_id=<id_3>)
```

## Verification

After staging multiple actions:

```bash
curl -s "http://localhost:8766/api/voice/pending?secret=<S>&tenant_id=<TID>"
# Should return 3 items, not 1
```
