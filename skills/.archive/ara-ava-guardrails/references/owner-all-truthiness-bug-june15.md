# `if owner:` Truthiness Bug — `'all'` As Literal Filter (June 15, 2026)

## Symptom

User creates action from navbar Actions page against Prashant Rai. Action appears on lead detail page (working) but NOT on the navbar Actions page's Pending tab (broken). API returns the action when called directly (`curl /api/actions?limit=5`), but the browser renders empty.

## Root Cause

The Pending tab's filter bar defaults to "All Owners" and "All Due Dates", which sends `owner=all&due=all` as URL params:

```js
// Frontend sends:
fetch('/api/actions?limit=50&owner=all&due=all&offset=0')
```

The backend endpoint treats `'all'` as a literal filter value:

```python
# server.py line 2664
if owner:                                    # 'all' is truthy → TRUE
    q = q.filter(ActionItem.owner == owner)  # filters for owner == 'all'
```

No ActionItem has `owner = 'all'` → query returns zero results → Pending tab shows empty.

The `due_window='all'` filter had the same issue (line 2673).

## Fix

Always check truthiness AND sentinel exclusion together:

```python
if owner and owner != "all":
    q = q.filter(ActionItem.owner == owner)

if due_window and due_window != "all":
    # apply due_window filter
```

## The Universal Pattern

Any FastAPI query parameter that accepts `'all'` as a "no filter" sentinel must use:
```python
if x and x != "all":    # ✅ Correct
```
Never:
```python
if x:                   # ❌ Treats 'all' as literal filter value
```

## Related

- Same bug exists for `channel`, `execution_state`, and any other filter that could receive 'all' from the UI
- The frontend defaults (`_actionFilters = { owner: 'all', due: 'all' }`) are the trigger — every fresh page load sends these
