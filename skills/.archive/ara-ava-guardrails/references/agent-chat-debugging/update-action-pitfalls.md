# Common Pitfalls: update_action + Timezone

Discovered June 16, 2026.

## update_action Silent Failures

**Symptom**: Ava calls `update_action`, tool returns "FAIL" with empty error. She retries 3 times, all fail.
**Root cause chain**:
1. LLM passes `due_at` as a string (e.g., `"2026-06-16T13:30:00"`)
2. SQLAlchemy DateTime column expects a Python `datetime` object
3. `TypeError: SQLite DateTime type only accepts Python datetime and date objects as input`
4. First crash poisons the DB session → all retries fail with `PendingRollbackError`
**Fix**:
```python
if "due_at" in args:
    raw = args["due_at"]
    if isinstance(raw, str):
        from datetime import datetime as _dt
        action.due_at = _dt.fromisoformat(raw)
    else:
        action.due_at = raw
```
Also add `db.rollback()` in the except block to clear poisoned session.

## get_action_items — Missing Action IDs

**Symptom**: Ava finds actions via `get_action_items` but can't `update_action` because she doesn't have the ID. She resorts to raw SQL (`query_database`) and hallucinates column names like `lead_name` or `title` that don't exist on the `action_items` table.

**Fix**: `get_action_items` now outputs `[id=XXXXXXXX]` with each action, and shows `due: Jun 16 11:30 AM UTC`.

## SQL Hallucination Patterns

When Ava can't find data through proper tools, she falls back to `query_database` with raw SQL. Common hallucinated column names:
- `lead_name` on `action_items` table (doesn't exist — lead is linked via `ref_id`)
- `title` on `scheduled_actions` table (doesn't exist)
- `ILIKE` operator (SQLite doesn't support it — use `LIKE` with case-insensitive collation, or `LOWER()`)

**Defense**: Always give Ava proper tools that return IDs. Don't make her guess SQL.

## Timezone: IST→UTC Confusion

**Symptom**: Ava passes "5 PM" as `"2026-06-16T17:00:00"` but server treats it as UTC → stored as 5 PM UTC = 10:30 PM IST.

**Fix**: System prompt now includes explicit IST→UTC conversion table:
```
IST to UTC: SUBTRACT 5h30m
  9 AM IST = 03:30 UTC    5 PM IST = 11:30 UTC
  6 PM IST = 12:30 UTC    10:30 PM IST = 17:00 UTC
```

**Debugging tip**: When checking due times in the DB, convert UTC→IST by ADDING 5h30m. `13:30 UTC = 7:00 PM IST`.
