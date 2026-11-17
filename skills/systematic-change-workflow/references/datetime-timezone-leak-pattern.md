# ARA Datetime Timezone Leak Pattern

## The Bug Class

Datetime values stored in UTC in the database are displayed to users in UTC
instead of the tenant's timezone (Asia/Kolkata / IST). This makes reminder
times, due dates, scheduled times, and activity timestamps off by 5.5 hours.

## Root Cause

ARA uses a dual timezone model:
- **Database**: All datetimes stored as naive UTC (no tzinfo)
- **Display**: All user-facing datetimes must be in tenant timezone (IST)

The conversion MUST happen at every output boundary. When it doesn't, users see
"due 2026-06-16 03:30" instead of "due Jun 16, 09:00 AM IST".

## Three Leak Patterns

### Pattern 1: `.isoformat() + "Z"` — Falsely claiming UTC
```python
# WRONG — shows raw UTC with false "Z" suffix
"due_at": (a.due_at.isoformat() + "Z") if a.due_at else None,
# ⇒ "2026-06-16T03:30:00Z"  (wrong — this is naive UTC, not actual UTC)

# RIGHT — converts to tenant timezone ISO
"due_at": to_ist(a.due_at) if a.due_at else None,
# ⇒ "2026-06-16T09:00:00+05:30"  (correct IST)
```

### Pattern 2: `.strftime()` on naive UTC datetime
```python
# WRONG — formats naive UTC directly
dt = c.created_at.strftime('%b %d %I:%M%p')
# ⇒ "Jun 16 03:30AM"  (wrong — this is UTC, should be 09:00 AM)

# RIGHT — converts to IST before formatting
dt = (c.created_at + IST_OFFSET).strftime('%b %d %I:%M%p')
# ⇒ "Jun 16 09:00AM"  (correct IST)
```

### Pattern 3: `str(dt)[:N]` — Raw string slicing
```python
# WRONG — raw string from naive UTC
"created_at": str(d.created_at)[:10]
# ⇒ "2026-06-16"  (might be wrong date near midnight)

# RIGHT — convert first, then slice
"created_at": to_ist(d.created_at)[:10]
# ⇒ "2026-06-16"  (correct IST date)
```

## The Helpers (Centralized — June 2026 Consolidation)

**Before June 23:** 21+ ad-hoc conversion sites using either `timedelta(hours=5, minutes=30)` (hardcoded) or `IST_OFFSET` (named constant but duplicated). Same bug kept recurring because each site was maintained independently.

**After June 23 consolidation** (v49): All conversions centralized into 3 functions in `app/config.py`:

```python
# In app/config.py
_IST_TD = timedelta  # re-exported for config-level helpers

def ist_to_utc(dt: datetime) -> datetime:
    """Convert IST-naive → UTC-naive. Subtracts 5:30. None-safe."""
    if dt is None: return None
    return dt - _IST_TD(hours=5, minutes=30)

def utc_to_ist(dt: datetime) -> datetime:
    """Convert UTC-naive → IST-naive. Adds 5:30. None-safe."""
    if dt is None: return None
    return dt + _IST_TD(hours=5, minutes=30)

def parse_due_at(value: str | None) -> datetime | None:
    """Parse a due_at string. If date-only (no T), defaults time to 18:00.
    Converts IST (user input) → UTC for storage. Returns None if empty."""
    if not value: return None
    if isinstance(value, str) and 'T' not in value:
        value += 'T18:00:00'
    return ist_to_utc(datetime.fromisoformat(value))
```

| Helper | Location | Input | Output | Use for |
|--------|----------|-------|--------|---------|
| `to_ist(dt)` | config.py | naive UTC | ISO string in tenant tz | API responses (legacy) |
| `ist_to_utc(dt)` | config.py | naive IST | naive UTC | Storing user input to DB |
| `utc_to_ist(dt)` | config.py | naive UTC | naive IST | Displaying DB values to user |
| `parse_due_at(str)` | config.py | ISO string | naive UTC (converted) | Parsing due_at from any source |
| `_format_utc_as_ist(dt)` | server.py | naive UTC | "Jun 16 09:00 AM IST" | Chat messages, LLM text |

**Migration pattern:**
```python
# BEFORE (scattered):
due_at = due_at - timedelta(hours=5, minutes=30)
due = due - IST_OFFSET
(dt + IST_OFFSET).strftime('%b %d')

# AFTER (centralized):
due_at = ist_to_utc(due_at)
due = ist_to_utc(due)
utc_to_ist(dt).strftime('%b %d')
```

## Audit Command

To find ALL remaining leaks in one pass:
```bash
ssh root@46.224.132.99 'grep -n "isoformat() + .Z.\|\.strftime\|str([a-z]*\.created_at)\[:.*\]\|str([a-z]*\.due_at)\[:.*\]\|utcnow() + timedelta(hours=5" /opt/ara/server.py'
```

Zero matches = clean. Any match = needs investigation.

## Verification After Fix

After fixing, re-run the audit grep. Then test:
1. Check reminder text: "due Jun 16, 09:00 AM IST" not "due 2026-06-16 03:30"
2. Check API response: `"due_at": "2026-06-16T09:00:00+05:30"` not `"2026-06-16T03:30:00Z"`
3. Check dashboard: times match local IST clock, not UTC

## June 2026 Cleanup: 22 Leaks Fixed

| Leak type | Count | Fixed with |
|-----------|-------|------------|
| `.isoformat() + "Z"` | 8 | → `to_ist()` |
| `.strftime()` on naive UTC | 12 | → `(dt + IST_OFFSET).strftime()` |
| `str(dt)[:N]` | 2 | → `to_ist()[:N]` |
| Hardcoded `+5:30` | 2 | → `datetime.now(IST_TZ)` |
| Reminder due time in UTC | 1 | → `_format_utc_as_ist()` |
| `str(action.due_at)[:19]` | 1 | → `_format_utc_as_ist()` |

## Downstream Pitfall: JS `+ 'Z'` Breaks After `to_ist()` Change

When `to_ist()` was changed to return timezoned ISO strings (`2026-06-16T09:00:00+05:30`)
instead of naive UTC (`2026-06-16T03:30:00`), the dashboard JS still appended `'Z'`:
```javascript
// BROKEN after to_ist() started adding +05:30
var dueStr = new Date(a.due_at + 'Z')  // "2026-06-16T09:00:00+05:30Z" — unparseable!
```

**Fix:** Remove `+ 'Z'` from JS. Let `to_ist()` handle timezone.
```javascript
// CORRECT
var dueStr = new Date(a.due_at)  // "2026-06-16T09:00:00+05:30" — parseable
```

**Lesson:** When changing a serialization format, grep downstream consumers
(JS `+ 'Z'`, template `datetime.strptime`, etc.) and update them together.

## Specific Pitfalls Discovered (June 2026)

### Pitfall 1: `create_action_item` tool skips IST→UTC for date-only strings

```python
# BUG: Only converts when string has a time component
if len(due_at_str) > 10:  # "2026-06-23" → len=10 → SKIPS CONVERSION
    due = due - IST_OFFSET
# Date-only strings are stored as midnight UTC instead of 18:30 UTC

# FIX: Use parse_due_at() — handles date-only, defaults to 18:00
due = parse_due_at(due_at_str)
```

### Pitfall 2: `set_cron` tool uses UTC clock as IST

```python
# BUG: utcnow() returns UTC, but hour/minute are IST values
now = utcnow()
first_at = now.replace(hour=18, minute=30)  # 18:30 UTC = midnight IST!

# FIX: Convert to IST, apply time, convert back
now = utcnow()
ist_now = utc_to_ist(now)
first_at = ist_now.replace(hour=18, minute=30)
first_at = ist_to_utc(first_at)
```

### Pitfall 3: Blast guard needed after timezone fixes

When fixing timezone bugs that caused ScheduledActions to fire at the wrong time,
correcting the `scheduled_at` values can cause MULTIPLE past-due SAs to fire
immediately on the next scheduler tick — bombarding the user with WhatsApp messages
at 6 AM. Always pair timezone fixes with a per-owner rate limit (max 3
`whatsapp_to_owner` per 60s).

When adding a notification type (e.g. `action_reminder`), it must be added to **three places**
simultaneously or the bell won't show it:

1. **Backend `actionable_types` set** in `/api/learning/notifications` — filters out non-actionable types
2. **JS badge poller `types=` param** in `loadNotifBadge()` — limits which types are counted
3. **Any post-filter** that checks ref_type/ref_id for stale references

Missing any one → bell shows 0 even when notifications exist in DB.
