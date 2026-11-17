#!/usr/bin/env python3
"""
Write-path gate for ARA dashboard.js — prevents shell pipe corruption.

Usage:
  python3 safe_write.py /opt/ara/static/dashboard.js

Reads proposed content from stdin. Validates before writing.
Rejects writes that are too small, missing key functions, or invalid JS.
Backs up before overwriting.

Exit codes:
  0 — Write succeeded
  1 — Validation failed (content rejected, file unchanged)
  2 — Usage error
"""
import subprocess, sys, os, shutil
from datetime import datetime

PATH = sys.argv[1] if len(sys.argv) > 1 else "/opt/ara/static/dashboard.js"

content = sys.stdin.read()
if not content:
    print("ERROR: No content on stdin")
    sys.exit(2)

print(f"Validating {len(content)} bytes for {PATH}...")

failures = 0

# Gate 1: File size sanity
if len(content) < 10000:
    print(f"  REJECT: Too small ({len(content)} bytes) — possible truncation")
    failures += 1

# Gate 2: Key patterns must exist
for pattern in ["renderActionsPage", "showActionsTab", "document.addEventListener"]:
    if pattern not in content:
        print(f"  REJECT: Missing required pattern: {pattern}")
        failures += 1

# Gate 3: Valid JavaScript
tmp = f"/tmp/dashboard_validate_{os.getpid()}.js"
with open(tmp, "w") as f:
    f.write(content)

r = subprocess.run(["node", "-c", tmp], capture_output=True, text=True)
os.unlink(tmp)

if r.returncode != 0:
    print(f"  REJECT: node -c failed:")
    print(f"  {r.stderr[:300]}")
    failures += 1

# Gate 4: ESLint strict check (if available)
eslint = shutil.which("eslint")
if eslint:
    with open(tmp, "w") as f:
        f.write(content)
    r = subprocess.run(
        [eslint, "--env", "browser,es2020", "--parser-options=ecmaVersion:2020",
         "--rule", '{"no-unreachable":"error","no-extra-boolean-cast":"error"}', tmp],
        capture_output=True, text=True, timeout=30
    )
    os.unlink(tmp)
    if r.returncode != 0 and "error" in r.stdout.lower() and "✖" in r.stdout:
        print(f"  ESLint errors found:")
        for line in r.stdout.split("\n")[:5]:
            print(f"    {line}")
        failures += 1

if failures > 0:
    print(f"\n{failures} GATE(S) FAILED — content rejected. File unchanged.")
    sys.exit(1)

# Backup existing file
if os.path.exists(PATH):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"{PATH}.bak.{ts}"
    shutil.copy2(PATH, bak)
    print(f"  Backup: {bak}")

# Write
with open(PATH, "w") as f:
    f.write(content)

# Verify write
with open(PATH) as f:
    written = f.read()
if written != content:
    print("  REJECT: Write verification failed — content mismatch")
    sys.exit(1)

print(f"  ✓ {len(content)} bytes written to {PATH}")
print("ALL GATES PASSED — write successful")
