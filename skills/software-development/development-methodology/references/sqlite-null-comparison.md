# SQLite + SQLAlchemy NULL Comparison Pitfall

## The Bug

`Column != "value"` silently excludes rows where the column is NULL.

```python
# ❌ BROKEN — silently drops NULL rows
ActionItem.outcome_state != "resolved"
```

In SQLite (and most SQL databases), `NULL != 'resolved'` evaluates to `NULL` (unknown), not `TRUE`. SQLite treats NULL as "falsy" in WHERE clauses, so NULL rows are excluded.

This means:
- If `outcome_state` is `NULL` (never set) — row is dropped
- If `outcome_state` is `"pending"` — row passes (expected)
- If `outcome_state` is `"resolved"` — row is dropped (expected)

The bug is silent — no error, just fewer rows than expected. Your query that should return 5 rows returns 0 or 2, and you assume the data isn't there.

## The Fix

```python
from sqlalchemy import or_

# ✅ CORRECT — includes NULL rows
or_(ActionItem.outcome_state != "resolved", ActionItem.outcome_state.is_(None))
```

This explicitly says: "either the value is not 'resolved', or it's NULL." Both conditions capture the intent.

## Detection Pattern

When a SQLAlchemy filter returns fewer rows than expected and the filtered column is nullable, suspect this immediately:

```bash
# 1. Check actual data
python3 -c "
from database import init_db, ActionItem
db = init_db()
items = db.query(ActionItem).all()
for a in items:
    print(f'{a.id}: outcome_state={repr(a.outcome_state)}')
db.close()
"

# 2. If any outcome_state is None but the query with != returns 0 rows → this bug
```

## Real Case (ARA, Jun 2026)

`GET /api/tenants/{id}/leads` added a "next_action" field — the most urgent pending/approved action per lead. Filter:
```python
ActionItem.execution_state.in_(["pending", "approved"]),
ActionItem.outcome_state != "resolved"
```

All test actions had `outcome_state = None` (never set). The `!= "resolved"` filter dropped them silently. Fixed with `or_(..., Column.is_(None))`.
