# Test Self-Cleaning (June 2026)

## Problem

Test suites (drift, roundtrip) created test actions marked with `[REGRESSION]` and `[REGRESSION T5]` titles but never deleted them. Residual test data accumulated in the production database with every test run.

## Fix Pattern

Add a CLEANUP block at the end of every test file that deletes what it created:

```python
# ── CLEANUP: Remove test residue ──
import urllib.request
try:
    actions = urllib.request.urlopen("http://localhost:8766/api/actions").read()
    import json
    data = json.loads(actions)
    for a in data.get("actions", []):
        title = a.get("title", "")
        if "REGRESSION" in title:
            aid = a["id"].replace("action_", "")
            req = urllib.request.Request(
                f"http://localhost:8766/api/actions/{aid}",
                method="DELETE"
            )
            urllib.request.urlopen(req)
except Exception:
    pass
```

## Covered Tests

- `test_action_item_drift.py` — creates 6 REGRESSION actions → CLEANUP removes all 6
- `test_write_path_roundtrip.py` — creates 1 REGRESSION T5 action → CLEANUP removes it
- `test_baileys_init.py` — no residue (import-only test)

## Verification

After running the suite, verify zero REGRESSION actions remain:
```sql
SELECT count(*) FROM action_items WHERE title LIKE '%REGRESSION%';
```
