"""
Dashboard integrity test — catches frontend corruption that server-side tests miss.
Added to release cycle: runs after every sprint deploy. Zero dependencies beyond Python stdlib + curl.
"""
import subprocess, sys

BASE = "http://localhost:8766"
FAIL = 0

def ok(label, condition, detail=""):
    global FAIL
    if condition:
        print(f"  PASS: {label}")
    else:
        print(f"  FAIL: {label} {detail}")
        FAIL += 1

# 1. Dashboard HTML loads
r = subprocess.run(["curl", "-sf", f"{BASE}/dashboard"], capture_output=True, text=True, timeout=10)
ok("Dashboard 200", r.returncode == 0)
ok("Has dashboard.js", '/static/dashboard.js' in r.stdout)
ok("Has navigation", 'nav-item' in r.stdout)

# 2. JS file served, non-truncated
r = subprocess.run(["curl", "-sf", f"{BASE}/static/dashboard.js"], capture_output=True, text=True, timeout=10)
ok("JS > 10KB", len(r.stdout) > 10000, f"={len(r.stdout)}b")
ok("JS starts with code", r.stdout[:20].strip().startswith(("var", "//", "/*", "function", "document")))

# 3. Syntax gate
r2 = subprocess.run(["node", "-c", "/opt/ara/static/dashboard.js"], capture_output=True, text=True)
ok("node -c passes", r2.returncode == 0, r2.stderr[:80])

# 4. Key functions present
for fn in ["renderActionsPage", "showActionsTab", "renderHistoryTab", "renderPendingTab"]:
    ok(f"Has {fn}", fn in r.stdout)

# 5. Critical API endpoints
for ep in ["/api/action-items/stats", "/api/action-items?status=resolved", "/api/action-items?status=dismissed"]:
    r = subprocess.run(["curl", "-sf", f"{BASE}{ep}"], capture_output=True, text=True, timeout=10)
    ok(f"API {ep.split('?')[0]}", r.returncode == 0)

print(f"\n{'ALL PASS' if FAIL == 0 else f'{FAIL} FAILED'}")
sys.exit(min(FAIL, 1))
