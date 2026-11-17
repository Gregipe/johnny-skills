# Set-Cron Troubleshooting — June 2026

## Failure Chain: Voice Note → "System Error" Response

When Greg says "set a reminder" and Ava responds "cron tool hit a system error," the failure could be at ANY of these layers:

### Layer 1: Did the LLM call the tool?

Check the DB:
```sql
SELECT content FROM agent_chat_messages WHERE role='assistant'
ORDER BY created_at DESC LIMIT 3;
```

Check the log:
```bash
journalctl -u ara-server --no-pager | grep "ENFORCER\|SET_CRON"
```

**No `[TOOL_CALL: set_cron]` in response → enforcer failure:**
- Is `is_q=True`? The enforcer skips questions. Fixed in Iteration 5 — questions with data intent now fire the enforcer.
- Is `has_data_tool=True` but the tool name appears in TEXT not in a `[TOOL_CALL:]` block? The check is `'"tool": "' + t + '"' in response` — matches JSON format, not text mentions.

### Layer 2: Did the tool execute but fail?

Check the log for `SET_CRON EXECUTING` / `SET_CRON SUCCESS` / `SET_CRON EXCEPTION`.

**`SET_CRON EXCEPTION: cannot access local variable 'ScheduledAction'...` → Python 3.12 scoping:**
The `execute_tool` function has a late `from database import ScheduledAction` for another tool. Python 3.12 makes the name local for the whole function. The `set_cron` handler uses `ScheduledAction()` before that import line.

**Fix:** Add `from database import ScheduledAction` at the top of the set_cron block.

### Layer 3: Did the tool succeed but the LLM hallucinated failure?

Check if a ScheduledAction was actually created:
```sql
SELECT id, action_type, status, payload FROM scheduled_actions
ORDER BY created_at DESC LIMIT 5;
```

If a row exists with `__morning_briefing__` as the message — the cron IS set. The LLM is hallucinating "system error" from conversation history poisoning.

**Fix:** Clean old hallucinated responses from the DB:
```sql
DELETE FROM agent_chat_messages WHERE content LIKE '%hit a system error%';
```

### Layer 4: Dashboard visibility

If the cron IS in the DB but not visible in the dashboard:
- Cron has `lead_id=None` (system-level, no lead attached)
- The Activities tab shows Conversations, not ScheduledActions
- The API at `/api/actions?status=pending` returns it — but the frontend may only display lead-scoped actions

## Quick Diagnostic Command

```bash
journalctl -u ara-server --no-pager | grep -E "ENFORCER|SET_CRON|Voice:" | tail -30
```

Expected happy path output:
```
Voice: sent interim message
SET_CRON executing: {title='Morning Briefing', ..., message='__morning_briefing__'}
SET_CRON SUCCESS: created abc123 for Morning Briefing
```

## Known Pitfalls

- **Duplicate voice notes** — 16+ identical messages in the thread poison the LLM. Fix: clean history + enable persistent dedup.
- **Conversation history poisoning** — "cron tool hit a system error" responses in the DB make the LLM repeat. Clean them AND add a prompt rule to ignore past failures.
- **set_cron tool description** — Must mention `__morning_briefing__` so the LLM knows dynamic content is possible. Update both the tool description (~line 5172) AND the tool summary (~line 5099).
