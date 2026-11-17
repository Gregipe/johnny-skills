# Pipeline Injection as a Contamination Vector

## New Failure Mode (Discovered June 17, 2026)

The Shriram Finance / Ajay Fageria contamination this session revealed a contamination vector distinct from conversation history poisoning: **pipeline injection alone can prime the LLM to act on entities that the user never mentioned.**

## How It Works

1. The system prompt injects the full pipeline: leads (13), deals (12), skills, documents
2. Ajay Fageria | Shriram Finance | new appears prominently in the leads list
3. Even with CLEAN conversation history (all Shriram assistant messages deleted), the LLM defaults to "Ajay" when confused
4. When Greg asked "would you be able to create a deal...?", the LLM proposed "let me create Ajay" — choosing the alphabetically-first "new" lead

## Root Cause

The pipeline data is concrete, specific, and action-oriented (leads have names, stages, phone numbers). The behavioral rules in the system prompt are abstract and procedural. When the LLM's attention is pulled, the concrete data wins over abstract rules.

This is fundamentally different from conversation history poisoning:
- **Conversation history poisoning**: Past LLM responses get re-read as input → self-reinforcing hallucination loop. Fix: delete contaminated messages from agent_chat_messages.
- **Pipeline injection contamination**: Live DB data in the system prompt primes the LLM toward specific entities. Fix: make classification framework strong enough to resist the pipeline's action bias.

## Fix: CLASSIFY INTENT FIRST

The new classification framework in the system prompt explicitly separates HYPOTHETICAL questions from COMMANDs. When the LLM classifies correctly (HYPOTHETICAL → "answer, never demonstrate"), it never reaches the pipeline data to act on it.

## Surgical Thread Cleanup Protocol

When an entity name has contaminated the conversation thread (the LLM keeps defaulting to it):

```sql
-- 1. Identify contaminated assistant messages
SELECT id, substr(content,1,150), created_at FROM agent_chat_messages 
WHERE thread_id=? AND role='assistant' 
AND (content LIKE '%EntityName%' OR content LIKE '%entityname%')
ORDER BY created_at;

-- 2. Delete ONLY assistant messages (keep user messages — those are Greg's)
DELETE FROM agent_chat_messages WHERE id IN (...);

-- 3. Cancel any stale pending actions from contamination
UPDATE action_items SET execution_state='cancelled', status='resolved',
    outcome_state='cancelled' WHERE id='...';
```

**Rule:** Never delete user messages. They're Greg's actual words and provide legitimate context. Only delete assistant messages that hallucinated or over-generated.

## Prevention

- The CLASSIFY INTENT FIRST framework prevents the LLM from reaching pipeline data for QUESTION/HYPOTHETICAL/CONVERSATION types
- The single-action guard prevents over-generation for COMMANDs
- Memory check (search_memory) before acting catches knowable context
- Search before guess rule prevents vague reference assumptions
