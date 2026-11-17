"""
Regression test: action item status/execution_state drift.
Run on production server: ssh root@46.224.132.99 'cd /opt/ara && python3 tests/test_action_item_drift.py'

Creates 5 test actions with varied status values (open, NULL, awaiting_approval).
Asserts the default /api/action-items endpoint returns ALL of them.
Currently FAILS: 3 of 5 dropped — proves the status="open" filter is too aggressive.
"""
import urllib.request, sqlite3, json, uuid, sys

URL = "http://localhost:8766/api/action-items"
DB = "/opt/ara/ara.db"
TENANT = "3e736242"

_p, _f = 0, 0

def check(label, condition, detail=""):
    global _p, _f
    if condition:
        _p += 1; print(f"  PASS {label}")
    else:
        _f += 1; print(f"  FAIL {label}" + (f" — {detail}" if detail else ""))

db = sqlite3.connect(DB)
test_ids = []

for exec_state, status_val, title in [
    ("pending", "open",               "[REGRESSION] exec=pending, status=open"),
    ("pending", None,                 "[REGRESSION] exec=pending, status=NULL"),
    ("fired",   "open",               "[REGRESSION] exec=fired, status=open"),
    ("fired",   None,                 "[REGRESSION] exec=fired, status=NULL"),
    ("pending", "awaiting_approval",  "[REGRESSION] exec=pending, status=awaiting"),
]:
    aid = uuid.uuid4().hex[:8]
    test_ids.append(aid)
    db.execute("""INSERT INTO action_items 
        (id, tenant_id, action_type, title, status, execution_state, 
         outcome_state, due_at, created_at)
        VALUES (?, ?, 'manual', ?, ?, ?, NULL, datetime('now', '+1 day'), datetime('now'))""",
        (aid, TENANT, title, status_val, exec_state))
db.commit()
print(f"Created {len(test_ids)} test action items\n")

def get_json(url):
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode())

resp = get_json(URL)
returned = {item["id"] for item in resp}

for tid in test_ids:
    check(f"Default: {tid} in response", tid in returned,
          "missing — silently dropped by status filter")
print(f"  Returned: {len(resp)} items, Created: {len(test_ids)}")

# Cleanup
for tid in test_ids:
    db.execute("DELETE FROM action_items WHERE id=?", (tid,))
db.commit(); db.close()

print(f"\n{'='*50}")
print(f"RESULTS: {_p} passed, {_f} failed")
sys.exit(1 if _f else 0)
