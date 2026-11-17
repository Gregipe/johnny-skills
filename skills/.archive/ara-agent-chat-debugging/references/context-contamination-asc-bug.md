# Coaching Context Contamination — ASC Bug (June 2026)

## Symptom
Ava responds with completely irrelevant suggestions from weeks-old conversations. "Which one — Dinesh Nagar lead, the Ramgopal catchup, or both?" when those names weren't mentioned in the current session.

## Root Cause
The agent chat endpoint loads coaching history with:
```python
recent_msgs = msg_query.order_by(AgentChatMessage.created_at.asc()).limit(50).all()
```
`asc()` loads the 50 **oldest** messages — the first messages ever stored become permanent context that appears in EVERY prompt. A June 18 conversation about Dinesh Nagar was loaded into a June 24 coaching session, causing the LLM to hallucinate from 6-day-old unrelated context.

## Fix
Change to `desc()` + reverse:
```python
recent_msgs = list(reversed(msg_query.order_by(AgentChatMessage.created_at.desc()).limit(50).all()))
```
This loads the 50 **most recent** messages. Old conversations age out naturally as new messages push them past the limit.

## Detection
```sql
SELECT count(*) FROM agent_chat_messages WHERE created_at < datetime('now', '-3 days');
-- 1270 old messages, 54 recent → ASC bug is active
```

If old > recent by a large margin and Ava is hallucinating week-old names, check the `order_by()` direction in the agent chat endpoint (~line 7001 in server.py).
