---
name: dashboard-integrity-gate
description: Pre- and post-deploy checks that prevent dashboard.js corruption from reaching users. Run before ANY dashboard change and after every sprint deploy.
---

## Dashboard Integrity Gate

**Run before any patch to dashboard.js and after every deploy.** This gate catches the regression that broke Sprint 3 — shell pipe escape mangling that passed `node -c` but failed in the browser.

### NEVER use shell pipes for JS

```
# WRONG — shell pipe mangles escaping:
hermes chat -q "..." | tee dashboard.js

# RIGHT — write to temp, validate, move:
hermes chat -q "..." > /tmp/dashboard_draft.js
cat /tmp/dashboard_draft.js | python3 /opt/ara/tests/safe_write.py /opt/ara/static/dashboard.js
python3 /opt/ara/tests/dashboard_integrity_test.py
```

### Pre-write Gate (safe_write.py)
Blocks writes that are:
1. Too small (<10KB) — truncation
2. Missing key functions (renderActionsPage, showActionsTab, document.addEventListener)
3. Invalid JavaScript (node -c)
4. Failing ESLint (if available)

### Post-write Verification (dashboard_integrity_test.py)
12 checks verifying the served dashboard is functional:
- Dashboard returns 200 with correct HTML
- dashboard.js is served and >10KB
- All key functions present
- node -c passes
- Critical API endpoints respond

### When to Run
- **Before**: any agent writes to dashboard.js — pipe through safe_write.py
- **After**: every sprint deploy — run dashboard_integrity_test.py
- **After any function rewrite (>50 lines)**: run backup feature audit — compare keywords against most recent backup to catch silent feature regression (see `references/backup-feature-audit.md`)
- **Mandatory**: Phase 7 of formal release cycle includes dashboard_integrity_test.py

### Files
- `/opt/ara/tests/safe_write.py` — pre-write validation gate
- `/opt/ara/tests/dashboard_integrity_test.py` — post-deploy integrity check
- `scripts/safe_write.py` — skill-bundled copy of the gate script
- `scripts/dashboard_integrity_test.py` — skill-bundled copy of the integrity test
- `references/backup-restore-checklist.md` — diff-before-revert procedure
- `references/backup-feature-audit.md` — keyword-based backup comparison for detecting silent feature regression

### Pitfalls

**Reverting to a backup loses features.** The Jun 15 backup of dashboard.js predated Sprint 2 — restoring it silently removed overdue detection from the actions table. ALWAYS diff the backup against the current version before reverting:
```
diff <(grep -c 'overdue\|isOverdue' current.js) <(grep -c 'overdue\|isOverdue' backup.js)
```
Check for: overdue detection, stateLabel logic, stateColor handling, recent feature additions. If features will be lost, extract the feature code from the corrupted version and re-apply, rather than reverting blindly.

**node -c is not enough — two distinct failure modes:**
  - **Escape mangling (Sprint 3):** `\\\\\\\"` → `\\\\\\\\\\\\\\\"` passed `node -c` but failed in browser with `Invalid escape in identifier`. Fix: `dashboard_integrity_test.py` verifies the served file.
  - **Silent function removal (June 20):** When dashboard.js is a single IIFE (`(function(){ ... })()`), removing function definitions does NOT produce syntax errors. `node -c` passes perfectly — the code is syntactically valid, just missing critical functions at runtime. On June 20, 8 functions were removed (16KB deleted) including the am-* event delegation handler, `editActionItem`, `saveEditedAction`, `deleteActionItem`, `_stripActionPrefix`, and the deal lead picker. The file passed `node -c`. The result: a frozen dashboard where nothing was clickable. **Fix:** after any function removal or rewrite >50 lines, run a function diff against the most recent backup: `diff <(grep -oP 'function \\w+' old.js | sort) <(grep -oP 'function \\w+' new.js | sort)`. Any line starting with `<` is a removed function.

**Feature regression on rewrite (June 2026).** The deal creation modal's lead picker (`addDealLeadPicker`, `_fillDealLead()`, autocomplete dropdown, readonly email/phone autofill) was silently lost when `showAddDealModal` was rewritten. The replacement used plain text inputs with no lead search. Detected by the user, not by tests. When rewriting any function, diff the old and new versions: list every `id=`, `onclick=`, and event listener in the old version and verify each is preserved. See `ara-ui-patterns` skill for the prevention checklist.

**SSH heredoc/Python escaping is unreliable.** Bash heredocs and `ssh ... "python3 -c '...'"` mangle quotes, backslashes, and special characters in dashboard.js patches. Never send Python scripts inline through SSH. Instead: write the script to a local file → `scp` it to the server → `ssh ... python3 /tmp/script.py`. This avoids all quoting issues and is the only reliable way to patch dashboard.js remotely.

**Function name collision.** `dashboard.js` is a single IIFE — all functions share one namespace. Before adding a new global function, grep for the proposed name to avoid collisions with existing functions in other sections. See `ara-ui-patterns` skill for the `markSelectedDone` collision example (June 2026).

### Greg's UI Preferences
- Font sizes: 11-12px for table content, 10px for secondary/tertiary text
- Colors: #6E6E73 (muted meta), #9A9A9E (tertiary), #dc2626 (overdue/error), #059669 (done/success)
- Layout: compact single-line rows, no dashboard-card wrapper on tables, flush with page
- New tables should match the actions table styling exactly
