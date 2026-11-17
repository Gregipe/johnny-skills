# SQLAlchemy NULL Comparison Pitfall

## The Bug

In SQL, `column != 'value'` **excludes** rows where `column IS NULL`. This is because SQL NULL comparison uses three-valued logic: `NULL != 'value'` evaluates to `UNKNOWN` (not `TRUE` or `FALSE`), so the row is excluded from results.

```python
# BROKEN — silently drops rows with NULL outcome_state
query = db.query(ActionItem).filter(
    ActionItem.outcome_state != "resolved",
)
# SQL: WHERE outcome_state != 'resolved'
# Result: rows with outcome_state IS NULL are EXCLUDED
```

## The Fix

Use `or_()` from SQLAlchemy to explicitly include NULL values:

```python
from sqlalchemy import or_

# FIXED — includes NULL outcome_state rows
query = db.query(ActionItem).filter(
    or_(ActionItem.outcome_state != "resolved", ActionItem.outcome_state.is_(None)),
)
# SQL: WHERE (outcome_state != 'resolved' OR outcome_state IS NULL)
# Result: all rows EXCEPT those with outcome_state = 'resolved'
```

## Where This Bit Us (ARA)

- **Next Action column** (leads list, Task 4): batch query returned 0 results because all `outcome_state` values were NULL. Fixed with `or_()`.
- **Notification engine** (Task 11-13): `_check_action_notifications()` found 0 due actions because the same filter excluded NULL outcome_state rows. Fixed with `or_()`.

## Detection Pattern

When a SQLAlchemy `.filter()` that uses `!=` returns **unexpectedly 0 results** while `SELECT *` shows rows exist, check whether the filtered column has NULL values. The fix is always the same: wrap the inequality in `or_(col != val, col.is_(None))`.

## test_build_tools_schema_returns_list Count

The test `test_build_tools_schema_returns_list` hardcodes a tool count: `assert len(schema) == 50`. When adding new tools, bump this number to match. Forgetting to update it causes a false-positive test failure.
