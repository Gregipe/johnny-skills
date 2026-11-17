# Tool Handler Safety Rules (June 2026)

When writing or modifying a tool handler in `execute_tool()`, audit for these common failure modes.

## 1. DateTime Columns — String from LLM, Datetime in DB

**Problem**: Tool schemas tell the LLM to output dates as `"YYYY-MM-DD"` strings (e.g., `"2026-06-16"`). The handler receives this as a string. SQLite's `DateTime` column rejects it:

```
TypeError: SQLite DateTime type only accepts Python datetime and date objects as input.
```

**Fix**: Parse date strings before INSERT. Pattern used by `create_action_item`:

```python
due_raw = args.get("due_at", None)
due = None
if due_raw and isinstance(due_raw, str):
    try:
        due = datetime.fromisoformat(due_raw)
        if len(due_raw) <= 10:  # date-only, default 9 AM
            due = due.replace(hour=9, minute=0, second=0)
    except (ValueError, TypeError):
        due = None
elif due_raw:
    due = due_raw  # already a datetime
```

**Applies to**: `create_action`, `create_action_item`, `set_reminder`, any handler with a `due_at` or date field.

## 2. NOT NULL Constraints — Audit Every Column

**Problem**: Some DB columns have NOT NULL constraints. If a handler doesn't set them, the INSERT crashes:

```
sqlite3.IntegrityError: NOT NULL constraint failed: action_items.action_type
```

**Fix**: Set `action_type` explicitly. Common values: `"manual"`, `"review_lead"`, `"note"`, `"stage_change"`, `"escalate"`, `"pending_confirmation"`.

```python
action = ActionItem(
    ...
    action_type="manual",  # REQUIRED — NOT NULL column
    ...
)
```

**Checklist for every new ActionItem INSERT**:
- `action_type` — NOT NULL
- `tenant_id` — NOT NULL  
- `execution_state` — defaults to None (fine)
- `due_at` — NULL allowed, but must be datetime if set
- `ref_type` / `ref_id` — NULL allowed, but should be set for lead-linked actions

## 3. `db.commit()` Failure Cascades

When a tool handler's `db.commit()` fails, SQLAlchemy rolls back the session. The confirmation flow's subsequent `db.commit()` then hits `PendingRollbackError`. The symptom is a 500 error with the *original* exception buried in the traceback. Always check the full traceback for the root cause — never stop at `PendingRollbackError`.
