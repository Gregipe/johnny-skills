# API Datetime: IST (Indian Standard Time) Formatting

ARA timestamps are stored as UTC-naive datetimes in SQLite. All API responses must convert them to IST (UTC+5:30) before serialization.

## The Pattern

Add this helper to `server.py` (near the top, after imports):

```python
IST_TZ = timezone(timedelta(hours=5, minutes=30))

def to_ist(dt):
    """Convert a UTC-naive datetime to IST-formatted ISO string."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST_TZ).isoformat()
```

Then replace every `.isoformat()` call in API responses with `to_ist()`:

```python
# Before:
"created_at": l.created_at.isoformat(),
"next_activity_at": r.scheduled_at.isoformat() + "Z" if r.scheduled_at else None,

# After:
"created_at": to_ist(l.created_at),
"next_activity_at": to_ist(r.scheduled_at) if r.scheduled_at else None,
```

## Rules

1. **All API responses** must use `to_ist()` — not just lead endpoints. This includes deals, conversations, skills, watchlist, scheduled actions, threads, and any future entity that returns timestamps.

2. **Remove `+ "Z"` suffix** — the IST offset (`+05:30`) makes the `Z` incorrect. `to_ist()` already includes the offset in the ISO string.

3. **Skip non-user-facing formats:**
   - `expiry_dt.isoformat()` for Google OAuth tokens (API-compatibility)
   - `.date().isoformat()` for date-only values
   - Internal-use datetimes that are never returned to the client

4. **Frontend:** The dashboard JS uses `.substring(0,10)` to extract dates from ISO strings. With IST, the date stays correct — timezones only shift the time component. No frontend changes needed.

## Bulk Replacement How-To

After adding the helper function, find all `.isoformat()` calls:

```bash
grep -n '\.isoformat()' server.py | grep -v 'def to_ist\|to_ist('
```

Replace each with `to_ist()` using the regex pattern: `\w+(?:\.\w+)+\.isoformat\(\)` → `to_ist($1)`. Handle `+ "Z"` suffix removal manually (the regex can strip it).
