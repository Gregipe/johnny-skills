# Advisor Integration Tests

After every sprint where the advisor flagged findings, write a targeted
integration test script that verifies EVERY finding directly against the
deployed code. This catches both (a) implementation errors and (b) advisor
false positives that were dismissed.

## Pattern (Python, runs on production server)

```python
"""Advisor-recommended integration tests — verifies every advisor finding."""
import subprocess, sys, json, urllib.request

BASE = "http://localhost:8766"
passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1; print(f"  PASS {name}")
    else:
        failed += 1; print(f"  FAIL {name} — {detail}")

# ── JS function unit tests (via node -e) ──
js_test = """
const fs = require('fs');
const src = fs.readFileSync('/opt/ara/static/dashboard.js','utf8');
const match = src.match(/function _stripActionPrefix\\([^)]+\\) \\{[^}]+\\}/s);
eval('var _stripActionPrefix = ' + match[0]);
console.log('action_test123 -> ' + _stripActionPrefix('action_test123'));
console.log('normal_id -> ' + _stripActionPrefix('normal_id'));
console.log('null -> ' + _stripActionPrefix(null));
"""
r = subprocess.run(["node", "-e", js_test], capture_output=True, text=True)
test("strips action_ prefix", " -> test123" in r.stdout)
test("passes through normal IDs", " -> normal_id" in r.stdout)
test("handles null", " -> null" in r.stdout)

# ── Function presence (read file directly) ──
dash = open("/opt/ara/static/dashboard.js").read()
test("editActionItem defined", "function editActionItem(" in dash)
test("old editAction removed", "function editAction(" not in dash)

# ── API route tests ──
# Test PATCH returns correct status
patched = api("/api/actions/some_id", "PATCH", {"title": "TEST"})
test("PATCH returns status=updated", patched.get("status") == "updated")

# ── Regression checks ──
test("addDealLeadPicker intact", "addDealLeadPicker" in dash)
test("bwAlert used, not alert()", dash.count("bwAlert(") >= 8)

# ── Summary ──
print(f"\nRESULTS: {passed}/{passed+failed}")
sys.exit(0 if failed == 0 else 1)
```

## Key techniques

1. **JS function unit tests via `node -e`** — extract a function with regex, `eval` it, call with test inputs. Doesn't require a browser.
2. **File content assertions** — `grep`-equivalent checks for function presence, keyword counts, specific patterns.
3. **API route tests via `urllib.request`** — no external deps, test GET/POST/PATCH/DELETE responses.
4. **Regression checks** — verify features that were previously lost (lead picker, am-* handlers) are still present.

## When to run

After every Phase 5 (implementation) and before Phase 7 (QA gate). Run via:
```bash
scp /tmp/advisor_tests.py root@46.224.132.99:/tmp/
ssh root@46.224.132.99 "python3 /tmp/advisor_tests.py"
```

## Pitfall: SSH subprocess in test scripts

When calling `subprocess.run(["ssh", "root@...", "curl ..."])` from a test
script running on the production server itself, the SSH call may fail because
the test is already ON the server. Prefer `subprocess.run("curl -s ...",
shell=True)` for local-to-server tests, and `urllib.request` for pure HTTP
tests (no subprocess at all).
