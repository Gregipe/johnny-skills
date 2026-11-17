# Coaching Context Window Bug

## Symptom
Ava responds with leads/context from weeks ago that have nothing to do with the current conversation. Example: Greg asks about pending actions → Ava asks "Which one — Dinesh Nagar lead, the Ramgopal catchup, or both?" when neither was mentioned in the current conversation.

## Root Cause
The coaching context loads messages with `order_by(created_at.asc()).limit(50)` — this loads the 50 OLDEST messages in the database, not the 50 most recent. Old coaching conversations from weeks ago are injected into every prompt.

## Fix
Change to `order_by(created_at.desc()).limit(50)` + reverse:
```python
recent_msgs = list(reversed(
    msg_query.order_by(AgentChatMessage.created_at.desc()).limit(50).all()
))
```
This loads the 50 MOST RECENT messages, then reverses to chronological order. Old conversations age out naturally.

## Verification
Check the date range of loaded messages:
```sql
SELECT role, created_at FROM agent_chat_messages ORDER BY created_at DESC LIMIT 5;
```
Messages should be from the last 1-2 days, not weeks ago.

## Related
- If hallucinations persist after this fix, check for `source_type` filtering that might exclude recent messages
- If messages are duplicated, check for thread_id filtering issues
- After fixing, purge contaminated coaching history from the old date range
