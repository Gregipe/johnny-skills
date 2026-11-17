# SQLite NULL Comparison Pitfall (June 2026)

## The Bug

In SQLite (and standard SQL), comparing `NULL != 'value'` returns `NULL` (not `True`). SQL WHERE clauses treat `NULL` as falsy, so:

```python
# ❌ BROKEN — NULL rows are silently excluded
q.filter(ActionItem.outcome_state != "resolved")
```

This looks correct but filters out ALL rows where `outcome_state IS NULL`. The `actions` API returned 0 results because every action had `outcome_state=None`.

## Real incidents

### 1. Actions API returning 0 results
**Location:** `GET /api/actions` (line 2730)

Original filter:
```python
q = db.query(ActionItem).filter(
    ActionItem.tenant_id == TENANT_ID,
    ActionItem.execution_state != "cancelled",
    ActionItem.outcome_state != "resolved",  # ← excludes NULL!
    ActionItem.status != "resolved",          # ← also excludes NULL!
)
```

**Fix:** Only filter by non-nullable columns, or use OR with IS NULL:
```python
q = db.query(ActionItem).filter(
    ActionItem.tenant_id == TENANT_ID,
    ActionItem.execution_state != "cancelled",
)
```

### 2. _build_recent_actions_block showing resolved actions
**Location:** `_build_recent_actions_block()` (line 5482)

Had no filter at all — ALL actions including resolved/cancelled were in LLM context.
**Fix:** Added `execution_state != "cancelled"` and `status != "resolved"`.
**Pitfall:** Adding `status != "resolved"` also has the NULL issue. If `status` can be NULL,
use:
```python
from sqlalchemy import or_
q.filter(or_(ActionItem.status != "resolved", ActionItem.status == None))
```

## Detection

When an API endpoint returns fewer results than expected, check:
1. Run the raw SQL: `SELECT * FROM action_items WHERE execution_state != 'cancelled'`
2. If DB returns rows but API returns 0, the filter has a NULL-excluding condition
3. Check all `!=` comparisons on nullable columns

## Rule of thumb

**Never use `!=` on a nullable column without `or_(col != val, col == None)`.**

Columns that are frequently NULL: `outcome_state`, `status`, `due_at`, `scheduled_action_id`, `deal_id`, `resolved_at`.
