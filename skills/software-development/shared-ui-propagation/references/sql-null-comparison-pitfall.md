# SQL NULL Comparison Pitfall (Propagation Failure)

## The bug

```python
# WRONG — silently drops all NULL rows
query.filter(ActionItem.outcome_state != "resolved")
```

SQL NULL comparisons return UNKNOWN (not TRUE), so `NULL != 'resolved'` evaluates to UNKNOWN and the row is EXCLUDED.

## The fix

```python
from sqlalchemy import or_

query.filter(or_(ActionItem.outcome_state != "resolved", ActionItem.outcome_state.is_(None)))
```

## Why this is a propagation failure

After fixing one query (leads list), the same pattern in the notification engine returned 0 results. The fix didn't propagate because we didn't grep for ALL instances of `!= "resolved"` across the codebase.

## Audit command

```bash
grep -n '!= "resolved"\|!= \\"resolved\\"' *.py
```

Every instance that filters on a nullable column needs the `or_(..., .is_(None))` guard.

## Known affected columns

- `ActionItem.outcome_state` (NULL until resolved)
- `ActionItem.execution_state` (rarely NULL, but defensively)
- Any column with `nullable=True` that gets compared with `!=`

## Recurrence history

- Jun 14: Fixed in leads list (Next Action column) — batch query returned 0
- Jun 14: Same bug in notification engine `_check_action_notifications()` — due_actions returned 0
