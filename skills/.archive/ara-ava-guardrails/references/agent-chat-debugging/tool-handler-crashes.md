# Tool Handler Crashes — Common Root Causes

When the confirmation flow logs `verdict: confirm` followed by a 500 error, the crash is almost always in the tool handler's `db.commit()`.

## #1: String `due_at` in DateTime column

**Symptom:**
```
TypeError: SQLite DateTime type only accepts Python datetime and date objects as input.
[SQL: INSERT INTO action_items (...) VALUES (..., '2026-06-16', ...)]
```

**Root cause:** The LLM outputs `due_at: "2026-06-16"` (a plain date string) because the tool schema explicitly says `"due_at": "YYYY-MM-DD"`. The `create_action` handler passes it directly to SQLAlchemy's DateTime column.

**Fix:** Parse `due_at` in the handler before the INSERT:
```python
_due_raw = args.get("due_at", None)
_due = None
if _due_raw and isinstance(_due_raw, str):
    try:
        _due = datetime.fromisoformat(_due_raw)
        if len(_due_raw) <= 10:  # date-only, default to 9 AM
            _due = _due.replace(hour=9, minute=0, second=0)
    except (ValueError, TypeError):
        _due = None
elif _due_raw:
    _due = _due_raw
```

The `create_action_item` handler already has this parsing. Check both handlers for consistency.

## #2: NULL `action_type` in NOT NULL column

**Symptom:**
```
sqlite3.IntegrityError: NOT NULL constraint failed: action_items.action_type
```

**Root cause:** The `create_action` handler doesn't set `action_type` in the ActionItem constructor. The DB column has a NOT NULL constraint.

**Fix:** Add `action_type="manual"` (or appropriate type) to the ActionItem instantiation. Other handlers use values like `"stage_change"`, `"review_qualification"`, `"review_lead"`, `"note"`.

## #3: PENDING_TTL too short

**Symptom:** The `CONFIRM-FLOW` log shows `prune: cancelled` immediately before `live-pending: NONE` — the user's "yes" arrived after the TTL expired. The LLM then treats "yes" as a new unrelated message and may hallucinate a completely different response.

**Root cause:** `PENDING_TTL = 120` (2 minutes) is too tight for voice note → proposal → user reads → types "yes".

**Fix:** Increase to 600 (10 minutes). The TTL is defined at the top of server.py.
