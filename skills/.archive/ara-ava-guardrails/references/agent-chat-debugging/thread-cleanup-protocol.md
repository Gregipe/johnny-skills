# Thread Cleanup Protocol — Surgical Deletion

## When to Use
When a name, concept, or failure message has contaminated the coaching thread's conversation history, causing Ava to hallucinate or fixate.

## Symptoms
- Ava references an entity/action NOT mentioned in the current exchange
- Ava says "X is still waiting on your yes" when X was already dealt with
- Ava conflates two unrelated requests because a name dominates thread attention
- Repeated tool-failure hallucination cascade (LLM reads own fake error → repeats it)

## How It Works

### 1. Identify contaminated messages
Query only assistant messages containing the contaminating term:
```sql
SELECT id, substr(content,1,150), created_at FROM agent_chat_messages 
WHERE thread_id=? AND role='assistant' 
AND (content LIKE '%Shriram%' OR content LIKE '%shriram%')
ORDER BY created_at;
```

### 2. Delete assistant messages only
```sql
DELETE FROM agent_chat_messages WHERE id IN (...);
```
NEVER delete user messages — those are Greg's actual words. Assistant messages are Ava's (potentially hallucinated) responses.

### 3. Clean junk messages
Also delete: failed tool-call responses, "Fair catch/pont" noise, cancelled-rejection responses that add no signal.

### 4. Verify
```sql
SELECT role, substr(content,1,120), created_at FROM agent_chat_messages 
WHERE thread_id=? ORDER BY created_at DESC LIMIT 15;
```
Thread should show clean exchange: user request → proposal → confirmation → result.

## The Attention Arithmetic
Each assistant message mentioning a name/concept adds to its attention weight. 5+ mentions of "Shriram Finance" in the last 20 messages → name dominates all ambiguous queries. The threshold for "too contaminated" is when the name appears >3x more than any other entity mention.

## Related
- `ara-ava-guardrails/references/conversation-history-poisoning.md` — the poisoning cascade theory
- `ara-agent-chat-debugging` — debugging context loss/contamination
