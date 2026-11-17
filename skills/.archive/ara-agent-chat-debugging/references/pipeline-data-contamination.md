# Pipeline Data Contamination (Jun 17, 2026)

## The Pattern

When pipeline data is injected into every LLM turn, the **alphabetically first lead/deal** in the "new" stage can dominate the LLM's attention. This creates a self-reinforcing contamination cycle:

```
Pipeline injects: "Ajay Fageria | Shriram Finance | new" (alphabetically first)
→ LLM fixates on this name when confused or greeting
→ Proposes creating Ajay Fageria / Shriram Finance deal
→ Thread gets contaminated with Ajay/Shriram references
→ Next turn: even MORE attention on Ajay/Shriram
→ Cycle repeats, growing stronger each turn
```

## Diagnosis

1. Check pending actions for repeated proposals of the same lead/deal:
```sql
SELECT execution_state, description, created_at FROM action_items 
ORDER BY created_at DESC LIMIT 20;
```

2. Check thread messages for contamination:
```sql
SELECT COUNT(*) FROM agent_chat_messages 
WHERE thread_id=? AND (content LIKE '%ContaminatedName%');
```

3. If the same names appear in every response regardless of user input, it's pipeline data contamination.

## Fix

1. **Delete the contaminated records from the DB** — not just thread messages, but the actual leads/deals:
```sql
DELETE FROM deals WHERE id='contaminated_deal_id';
DELETE FROM leads WHERE id='contaminated_lead_id';
```

2. **Delete all pending actions referencing those names:**
```sql
DELETE FROM action_items WHERE description LIKE '%ContaminatedName%';
```

3. **Delete all thread messages referencing those names:**
```sql
DELETE FROM agent_chat_messages WHERE content LIKE '%ContaminatedName%';
```

4. **Delete orphaned user messages** that triggered the contamination (otherwise the LLM sees unanswered messages and tries to respond):
```sql
DELETE FROM agent_chat_messages WHERE thread_id=? AND role='user' 
AND id NOT IN (SELECT DISTINCT ... ) -- careful: filter by context
```

## Related: Capability-List Priming

A separate but related pattern: when previous assistant responses contain capability lists ("Here's what I can do..."), the LLM is primed to respond to greetings with capability lists. This is thread-history priming, not pipeline-data contamination.

Fix: find and delete all capability-list responses from the thread:
```sql
DELETE FROM agent_chat_messages WHERE thread_id=? AND role='assistant'
AND (content LIKE '%I can create%' OR content LIKE '%I handle%' 
     OR content LIKE '%capabilit%' OR content LIKE '%Leads &%');
```
Then delete the orphaned user greetings that triggered those responses.
