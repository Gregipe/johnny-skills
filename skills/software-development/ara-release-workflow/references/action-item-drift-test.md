# Action Item Status/Execution State Drift Bug

## Summary

The `/api/action-items` endpoint defaults to filtering `status="open"` (server.py line 7214). Actions created through the modern two-axis path (setting `execution_state` without explicitly setting `status`) get silently dropped if `status` is NULL or any value other than "open".

## The Bug

```python
# server.py line 7210-7214
q = db.query(ActionItem).filter(ActionItem.tenant_id == TENANT_ID)
if status:
    q = q.filter(ActionItem.status == status)
else:
    q = q.filter(ActionItem.status == "open")  # ← drops NULL and non-"open" rows
```

## SQL NULL Trap

A naive "fix" like `status != "resolved"` ALSO drops NULL rows because `NULL != "resolved"` evaluates to NULL (not True) in SQL. The correct fix must use the two-axis filter:

```python
# Correct: filter on execution_state/outcome_state, not status string
q = q.filter(
    or_(
        ActionItem.execution_state.in_(["pending", "fired"]),
        ActionItem.outcome_state == None
    )
)
```

## Reproduction

1. Create action items with varied `status` values (open, NULL, awaiting_approval)
2. Hit `GET /api/action-items` (default, no status param)
3. Only items with `status="open"` are returned; others silently dropped

## Date Confirmed

June 19, 2026 — synthetic test proved 3 of 5 items dropped. Production data (13 rows) happens to all have `status="open"` so the bug hasn't fired yet, but it's a loaded gun.

## Regression Test

`scripts/test_action_item_drift.py` — creates 5 test actions, asserts all 5 are returned by the default endpoint. Currently FAILS (3 dropped). Run on the production server:

```bash
ssh root@46.224.132.99 'cd /opt/ara && python3 tests/test_action_item_drift.py'
```

## Related

- `test_action_item_drift.py` on the production server at `/opt/ara/tests/`
- ActionItem state triplex documentation in `ara-release-workflow` Part 3
