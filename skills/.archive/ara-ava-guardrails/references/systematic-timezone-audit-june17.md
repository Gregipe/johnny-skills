# Systematic Timezone Audit — June 17, 2026

## Problem
User-facing datetimes were leaking raw UTC in reminders, API responses, and notifications. Despite centralized helpers (`to_ist()`, `_format_utc_as_ist()`), multiple output paths bypassed them.

## Audit Pattern
To find ALL datetime leaks, grep for every output path that formats a datetime:

```bash
grep -n '\.isoformat()\|\.strftime\|str(.*due_at\|str(.*created_at\|str(.*scheduled_at\|\[:16\]\|\[:19\]' server.py
```

Categorize each hit:
1. **Already converted** — uses `to_ist()`, `IST_TZ`, or `(dt + IST_OFFSET)` → safe
2. **Needs fix** — uses `.isoformat() + "Z"`, `str(dt)[:N]`, or raw `.strftime()` on naive UTC → leak

## Fix Patterns

| Leak type | Fix |
|-----------|-----|
| `.isoformat() + "Z"` | → `to_ist(dt)` |
| `.strftime()` on naive UTC | → `(dt + IST_OFFSET).strftime(...)` |
| `str(dt)[:N]` | → `to_ist(dt)[:N]` or `_format_utc_as_ist(dt)` |
| `utcnow() + timedelta(hours=5, minutes=30)` | → `datetime.now(IST_TZ)` |

## Audit Results (June 17)
- 8 `.isoformat() + "Z"` places fixed → `to_ist()`
- 12 raw `.strftime()` on naive UTC fixed → `(dt + IST_OFFSET).strftime()`
- 2 `str(dt)[:N]` fixed → `to_ist()[:N]`
- 2 hardcoded `+ timedelta(hours=5, minutes=30)` fixed → `datetime.now(IST_TZ)`
- 1 reminder due time in UTC fixed → `_format_utc_as_ist()`
- **Zero leaks remain in user-facing output paths**

## Pitfall: Dashboard JS `+ 'Z'` append
The dashboard JS line `a.due_at + 'Z'` conflicted with `to_ist()` output (which already has `+05:30`). Adding `Z` created an invalid ISO string. Fixed by removing the `+ 'Z'` since `to_ist()` output is already timezone-aware.

## Pitfall: Notification message text
Reminder notifications in `learning_notifications` store the message body as text. Old notifications (before the fix) still contain raw UTC strings. Mark them as acknowledged/archived so only IST-formatted messages appear going forward.
