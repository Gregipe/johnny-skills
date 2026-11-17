# trigger_cadence ScheduledAction Shadowing — June 2026

## What Happened

Ava called `trigger_cadence("Gregory Ipe")` → crashed with:
```
❌ executing trigger_cadence: cannot access local variable 'ScheduledAction'
   where it is not associated with a value
```

## Root Cause

`execute_tool()` in server.py has 4 `from database import ScheduledAction` inside different tool handler branches (lines ~4027, 4127, 4339, 7126). Python treats ALL references to `ScheduledAction` in the function as local — even in branches that run BEFORE those imports. The `trigger_cadence` handler at ~line 3396 calls `db.query(ScheduledAction)` before any of those imports execute.

This is the same bug as:
- `Conversation` shadowing in `get_summary` handler (May 30 fix)
- `msg` shadowing in `email_utils.py` (May 30 fix)

## Fix Applied

Every local import got a unique alias:

| Line | Before | After |
|------|--------|-------|
| ~3396 | `pending = db.query(ScheduledAction)` | `from database import ScheduledAction as _SA_Cad; pending = db.query(_SA_Cad)` |
| ~4027 | `from database import ScheduledAction` | `from database import ScheduledAction as _SA_Dev` |
| ~4127 | `from database import ScheduledAction` | `from database import ScheduledAction as _SA_Msg` |
| ~4339 | Already `_SA` | ✅ OK |

## Verification

```bash
curl -s -X POST http://localhost:8766/api/cadence/trigger/lead/{lead_id}
# Returns: {"lead":"Gregory Ipe","cadence_type":"cold","scheduled":5,"note":""}
```

## Current State (June 12, 2026)

- ✅ Fix applied to production server at /opt/ara/server.py
- ✅ QA passed (254 tests, mypy clean, syntax OK)
- ✅ Trigger verfied working via API — 5 steps scheduled
- ❌ **NOT committed to git** — `git status` shows `M server.py`. Must be committed before next deploy.

## Detection Pattern

```bash
grep -n 'import.*ScheduledAction\|ScheduledAction.*import' server.py
```
