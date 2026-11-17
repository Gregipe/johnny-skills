# Self-Reinforcing Contamination Cycle (June 2026)

## The Pattern

When a specific name/entity appears prominently in both pipeline data AND conversation history, Ava enters a self-reinforcing hallucination loop:

1. **Pipeline injects "Ajay Fageria | Shriram Finance | new"** — alphabetically first in "new" stage
2. **LLM proposes creating them** — pipeline data is most salient, so LLM defaults to it
3. **Hallucinated Assistant message saved** — "⏳ Confirm? Create Ajay Fageria..."
4. **Thread contaminated** — Ajay/Shriram now in conversation history too
5. **Next turn: DOUBLE attention** — pipeline data + thread history both prime Ajay/Shriram
6. **Repeat and accelerate** — every turn adds more Ajay/Shriram references

## Why This Happens

- **Pipeline data is the most salient content** in Ava's context (13+ leads, 12+ deals)
- **Alphabetically first items get the strongest attention** — Ajay Fageria is first in "new" leads
- **The classification framework cannot resist pipeline pull** if they share the same context window
- **Each hallucination makes the next one MORE likely**, not less

## Detection

Run this query to check for contamination:
```sql
SELECT role, substr(content,1,80), created_at FROM agent_chat_messages 
WHERE thread_id='80123f1c' 
AND (content LIKE '%Ajay%' OR content LIKE '%Shriram%' OR content LIKE '%shriram%')
ORDER BY created_at DESC;
```

If count is > 2 and growing, the cycle is active.

Also check for stale pending actions:
```sql
SELECT id, execution_state, description FROM action_items 
WHERE description LIKE '%Ajay%' OR description LIKE '%Shriram%'
ORDER BY created_at DESC;
```

## Cleanup Protocol

**Step 1: Cancel all contaminated pending actions**
```sql
UPDATE action_items SET execution_state='cancelled', status='resolved', 
outcome_state='cancelled', resolved_at=datetime('now') 
WHERE description LIKE '%Ajay%' OR description LIKE '%Shriram%'
AND execution_state='awaiting_approval';
```

**Step 2: Delete ALL contaminated thread messages (BOTH user and assistant)**
```sql
DELETE FROM agent_chat_messages 
WHERE thread_id='80123f1c' 
AND (content LIKE '%Ajay%' OR content LIKE '%Shriram%' OR content LIKE '%shriram%');
```

**Step 3: Delete orphaned user messages from contamination window**
Messages from the contamination window that triggered hallucinated responses. These have no assistant response (we deleted the hallucinated ones in Step 2) and will confuse the LLM if left.

```sql
DELETE FROM agent_chat_messages 
WHERE thread_id='80123f1c' AND role='user' 
AND created_at > '<contamination_window_start>' 
AND content NOT LIKE '%[VOICE%';
```

**Step 4: Verify**
```sql
SELECT COUNT(*) FROM agent_chat_messages 
WHERE thread_id='80123f1c' 
AND (content LIKE '%Shriram%' OR content LIKE '%shriram%' OR content LIKE '%Ajay%');
```

Must return 0.

## Prevention

The cycle can only be prevented by one of:
1. **Delete/archive the contaminated entities from the pipeline** — removes them from injection
2. **Two-pass classification** — classify intent without pipeline data first, then inject pipeline only for COMMAND type
3. **Move contaminated entities to later stages** — so they're not alphabetically first in "new"

The thread cleanup alone is temporary — the next turn re-injects pipeline data and the cycle can restart.

## Real Case: June 17, 2026

- **Entity:** Ajay Fageria / Shriram Finance
- **Source:** Pipeline injection (alphabetically first "new" lead + matching deal)
- **Cycles:** 4+ full cleanup cycles in one session
- **Total messages deleted:** 21 contaminated + 5 orphaned user + 3 hallucinated proposals
- **Pending actions cancelled:** 5 (all proposing Ajay/Shriram)
- **Root cause:** Pipeline data + thread contamination create attention vortex
- **Temporary fix:** Full DB cleanup (messages + pending actions)
- **Permanent fix needed:** Two-pass classification OR archive Ajay/Shriram from pipeline
