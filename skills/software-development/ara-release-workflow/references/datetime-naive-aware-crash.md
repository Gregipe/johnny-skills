# Datetime Naive vs Aware Crash in Sort Keys

## Symptom
`TypeError: can't compare offset-naive and offset-aware datetimes` → 500 Internal Server Error → empty response → test JSON decode failure.

## Root Cause
`database.py::utcnow()` returns `datetime.now(timezone.utc)` — offset-aware.
SQLite stores datetimes as naive strings (e.g. `2026-06-17 04:39:19.017883`).
SQLAlchemy reads them back as naive Python datetime objects.
When used together in `sort(key=lambda r: r.resolved_at or r.created_at or now)`, Python can't compare aware vs naive → TypeError.

## Where It Hit
`_build_recent_actions_block()` in `server.py` at the `rows.sort(...)` line.
Called from `agent_chat()` during context assembly — so it crashes EVERY chat request, not just tests.

## Fix
Normalize all datetimes to naive before sorting:
```python
def _sort_key(r):
    dt = r.resolved_at or r.created_at
    if dt is None:
        return datetime.min
    return dt.replace(tzinfo=None) if hasattr(dt, 'tzinfo') and dt.tzinfo else dt
rows.sort(key=_sort_key, reverse=True)
```
This preserves proper datetime ordering (newest first) while avoiding the naive/aware TypeError.
String comparison was considered but rejected — it silently produces wrong order if timestamps aren't ISO 8601 (though ARA's are, it's fragile).

Requires `from datetime import datetime` at the top of the function.

## Audit Pattern
Any sort, comparison, or arithmetic involving both `utcnow()` and SQLite-stored datetimes is a potential crash. Check:
```bash
grep -n 'sort.*key.*lambda.*created_at\|sort.*key.*lambda.*resolved_at\|sort.*key.*lambda.*utcnow\|utcnow.*-.*created\|created.*-.*utcnow' server.py
```

## Prevention
Never mix `utcnow()` (aware) with raw DB datetimes (naive) in comparisons. Either:
1. Normalize both sides to naive before comparing (preferred — preserves real datetime ordering): `dt.replace(tzinfo=None) if dt.tzinfo else dt`
2. String comparison (simpler, works for ISO format, but fragile if format drifts)
3. Make both sides aware: `r.created_at.replace(tzinfo=timezone.utc)` (but DB may have IST values stored as UTC, creating offset bugs of the sort fixed by `to_ist()`)
