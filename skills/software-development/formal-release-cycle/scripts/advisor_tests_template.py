#!/usr/bin/env python3
"""Advisor integration tests — verifies every advisor finding against deployed code.

Pattern: after Phase 5 (implementation), run this on the production server to
confirm all advisor findings are addressed before Phase 7 (QA gate).

Usage:
    scp /tmp/advisor_tests_template.py root@46.224.132.99:/tmp/
    ssh root@46.224.132.99 "python3 /tmp/advisor_tests_template.py"
"""
import subprocess, sys, json, urllib.request, urllib.error

BASE = "http://localhost:8766"
passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS {name}")
    else:
        failed += 1
        print(f"  FAIL {name} — {detail}")

def api(path, method="GET", data=None):
    """Thin HTTP helper — no external deps."""
    url = f"{BASE}{path}"
    try:
        if method == "GET":
            r = urllib.request.urlopen(url, timeout=10)
            raw = r.read().decode()
        elif method == "PATCH":
            req = urllib.request.Request(url, data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"}, method="PATCH")
            r = urllib.request.urlopen(req, timeout=10)
            raw = r.read().decode()
        elif method == "DELETE":
            req = urllib.request.Request(url, method="DELETE")
            r = urllib.request.urlopen(req, timeout=10)
            raw = r.read().decode()
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()[:200]}
    except Exception as e:
        return {"error": str(e)[:200]}


# ═══════════════════════════════════════════════════════════════
# TEMPLATE TEST GROUPS — customize per sprint
# ═══════════════════════════════════════════════════════════════

# ── JS function unit tests (via node -e) ──
# Use this for client-side functions that have no API equivalent.
# Extract with regex, eval, call with test inputs.
print("\n═══ T1: JS function unit tests ═══")
# Example: test a prefix-stripping function
# js_test = """
# const fs = require('fs');
# const src = fs.readFileSync('/opt/ara/static/dashboard.js','utf8');
# const match = src.match(/function _stripActionPrefix\\([^)]+\\) \\{[^}]+\\}/s);
# if (!match) { console.log('FUNCTION_NOT_FOUND'); process.exit(1); }
# eval('var _stripActionPrefix = ' + match[0]);
# console.log('prefixed_id -> ' + _stripActionPrefix('prefixed_id'));
# """
# r = subprocess.run(["node", "-e", js_test], capture_output=True, text=True, timeout=10)
# test("function exists", "FUNCTION_NOT_FOUND" not in r.stdout)
# test("correct behavior", "expected_output" in r.stdout)

# ── Function presence (file content assertions) ──
print("\n═══ T2: Function presence ═══")
dash = open("/opt/ara/static/dashboard.js").read()
# test("feature X defined", "function featureX(" in dash)
# test("old function Y removed", "function oldY(" not in dash)

# ── API route sanity ──
print("\n═══ T3: API routes ═══")
# actions = api("/api/actions?limit=3").get("actions", [])
# test("GET /api/endpoint returns data", len(actions) > 0)
# if actions:
#     patched = api(f"/api/actions/{actions[0]['id']}", "PATCH", {"title": "TEST"})
#     test("PATCH returns status=updated", patched.get("status") == "updated")

# ── Regression checks ──
print("\n═══ T4: Regression checks ═══")
# test("feature from v46 intact", "addDealLeadPicker" in dash)
# test("feature from v45 intact", "_selectedActions" in dash)

# ── Code quality assertions ──
print("\n═══ T5: Code quality ═══")
# test("uses bwAlert not alert()", dash.count("bwAlert(") >= expected_count)
# test("no data-lead-id DOM scrape in restored fn", "data-lead-id" not in target_section)

# ── Event handler redirects ──
print("\n═══ T6: Event handler wiring ═══")
# test("am-edit calls correct function", 'correctFn(editBtn' in dash)
# test("am-delete calls correct function", 'correctFn(deleteBtn' in dash)

# ── Version serving ──
print("\n═══ T7: Dashboard version serving ═══")
# r = subprocess.run("curl -s http://localhost:8766/dashboard | grep -o 'dashboard.js?v=NUM'",
#     shell=True, capture_output=True, text=True, timeout=10)
# test("correct version served", "v=NUM" in r.stdout)

# ── Summary ──
total = passed + failed
print(f"\n{'='*50}")
print(f"RESULTS: {passed}/{total} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
