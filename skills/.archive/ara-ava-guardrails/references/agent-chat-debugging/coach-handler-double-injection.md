# Double User Message Injection Fix — June 2026

## Problem

Ava hallucinated "Acme Manufacturing" when Greg asked "which sector is this company in?" after being told the lead was from **Xpressbees**. The LLM lost pronoun resolution ("this company") and output a training-data artifact instead of the real company name.

## Root Cause

The coaching handler (`_handle_owner_coach_whatsapp`) saved the user message to the AgentChatMessage table BEFORE calling `agent_chat`. Then `agent_chat`:
1. Loaded the last 20 messages (which included the just-saved user message)
2. Appended `user_msg` again at line 4896

Result: LLM context had TWO identical user messages back-to-back:
```
Assistant: "Gregory Ipe from Xpressbees..."
User: "which sector is this company in?"    ← from DB
User: "which sector is this company in?"    ← appended again
```

Duplicate user messages confuse the LLM's pronoun resolution → hallucination.

## Fix Applied

**File:** `server.py`

Removed the `AgentChatMessage(role="user", ...)` save block from `_handle_owner_coach_whatsapp` (lines 7889-7897):

```python
# REMOVED:
msg = AgentChatMessage(
    thread_id=thread.id,
    tenant_id=TENANT_ID,
    role="user",
    content=message,
)
db.add(msg)
db.commit()
```

`agent_chat` already handles saving user + assistant messages at line 5065-5067 of `server.py`. The pre-save was redundant and caused the double-injection.

## Files Modified

- `server.py` — removed pre-save of user message in `_handle_owner_coach_whatsapp`
- `server.py` — also removed duplicate assistant message save (same function was also saving the assistant response a second time)

## Verification

- Check DB: only ONE `AgentChatMessage` entry per user query
- Replicate: ask about a lead, then ask "what sector is this company in?" → should resolve to the correct company
