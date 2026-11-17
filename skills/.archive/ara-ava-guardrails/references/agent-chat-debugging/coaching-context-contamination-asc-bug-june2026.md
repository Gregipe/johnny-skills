# Coaching Context Contamination — ASC Bug (June 2026)

## Symptom

Ava hallucinates names and proposals from WEEKS-OLD conversations. Example: "Which one — Dinesh Nagar lead, the Ramgopal catchup, or both?" — neither name appeared in the current conversation. They were from June 18 coaching messages.

## Root Cause

In `/api/agent/chat/{tenant_id}` at line ~7001 in server.py:

```python
recent_msgs = msg_query.order_by(AgentChatMessage.created_at.asc()).limit(50).all()
```

**`asc()` loads the 50 OLDEST messages**, not the 50 most recent. With 1,324 messages in the table, the first 50 were from May 25-June 16 — containing stale conversations about Dinesh Nagar, Ramgopal, etc. These were injected into EVERY coaching prompt.

## Fix

```python
recent_msgs = list(reversed(msg_query.order_by(AgentChatMessage.created_at.desc()).limit(50).all()))
```

Changed from `asc().limit(50)` to `desc().limit(50)` + `reversed()`. Now loads the 50 MOST RECENT messages in chronological order.

## Verification

| Method | Date range | Messages |
|--------|-----------|----------|
| OLD `asc` | May 25 → Jun 16 | 50 oldest |
| NEW `desc+reverse` | Jun 22 → Jun 24 | 50 most recent |

## Detection

If Ava produces names/proposals from conversations older than 2 days that don't appear in the current thread, suspect this bug. Check: `SELECT role, created_at FROM agent_chat_messages WHERE tenant_id = '...' ORDER BY created_at ASC LIMIT 50` — if dates are old, the fix hasn't been applied.
