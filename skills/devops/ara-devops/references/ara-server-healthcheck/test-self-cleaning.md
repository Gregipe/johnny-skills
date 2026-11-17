# Test Suite Self-Cleaning

The drift test (`test_action_item_drift.py`) and roundtrip test (`test_write_path_roundtrip.py`) create real ActionItems in the production database. Each run leaves 6+ actions with `[REGRESSION]` in the title.

**Fix applied June 2026:** Both tests now call `remove_test_actions()` before `sys.exit(0)`, which queries `/api/actions` for any action containing `[REGRESSION]` in the title and DELETE's them.

**To add self-cleaning to a new test:**
```python
import urllib.request, json
try:
    req = urllib.request.Request("http://localhost:8766/api/actions?limit=100")
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    for a in data.get("actions", []):
        if "[REGRESSION]" in (a.get("title") or ""):
            req2 = urllib.request.Request(
                f"http://localhost:8766/api/actions/{a['id']}", method="DELETE")
            urllib.request.urlopen(req2, timeout=5)
except Exception as e:
    print(f"CLEANUP: {e}")
```

**Verification:** Run the test, then check:
```sql
SELECT count(*) FROM action_items WHERE title LIKE '%REGRESSION%';
```
Must return 0.