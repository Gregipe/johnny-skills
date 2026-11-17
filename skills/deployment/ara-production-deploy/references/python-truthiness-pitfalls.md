# Python Truthiness Pitfalls in SQLAlchemy Filters

## 1. `"all"` is truthy — zero-result bug

When filtering with optional string params from frontend dropdowns, `if owner:` treats the literal string `"all"` as truthy. It filters for rows where `owner == "all"` — which matches nothing.

**Symptoms:** List endpoints return empty results when filters default to "all" (e.g., `owner=all&due=all` from frontend filter dropdowns).

**Fix:** Always add the no-op check:
```python
# ❌ Silently filters to zero rows when owner="all"
if owner:
    q = q.filter(ActionItem.owner == owner)

# ✅ Skips filter for the "all" sentinel
if owner and owner != "all":
    q = q.filter(ActionItem.owner == owner)
```

This applies to ANY filter param that uses "all" as a "no filter" sentinel value. Same pattern for `due_window`, `channel`, `status`, etc.

## 2. `NULL != "string"` silently excludes NULL rows

`Column != "resolved"` returns UNKNOWN (not TRUE) for NULL values. SQL includes only TRUE rows in results — NULL rows are silently dropped.

**Fix:**
```python
# ❌ Silently drops NULL rows
q = q.filter(ActionItem.outcome_state != "resolved")

# ✅ Correct — includes NULL rows
from sqlalchemy import or_
q = q.filter(or_(ActionItem.outcome_state != "resolved", ActionItem.outcome_state.is_(None)))
```

## Diagnostic pattern

When an API endpoint that should return N rows returns 0 instead:
1. Curl the endpoint directly with the exact query params the frontend sends
2. Break the query into individual filter conditions
3. Check each filter for truthiness traps (`"all"`, empty string, `NULL` comparison)