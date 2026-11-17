# Systematic Timezone Audit for Datetime Output Paths

**Why this exists:** Greg's ARA CRM stores datetimes in UTC but ALL user-facing output must show tenant timezone (IST). Despite multiple point fixes, UTC leaked through in 29+ places — `.isoformat() + "Z"` falsely claiming UTC, raw `.strftime()` on naive datetimes, `str(dt)[:N]` string slicing. Each leak was patched individually until the full audit on June 17, 2026.

## The Audit Pattern

### Step 1: List all datetime output paths
```bash
grep -n 'to_ist\|isoformat()\|strftime\|str(.*due_at\|str(.*created_at\|str(.*scheduled_at\|\[:16\]\|\[:19\]' server.py | grep -v '^#'
```

### Step 2: Categorize every occurrence
| Pattern | Problem | Fix |
|---------|---------|-----|
| `dt.isoformat() + "Z"` | Falsely claims UTC timezone. Frontend interprets as UTC, user sees wrong time. | `to_ist(dt)` |
| `dt.strftime(...)` on naive UTC | Shows UTC hours (5.5h off for IST). | `(dt + IST_OFFSET).strftime(...)` or `_format_utc_as_ist(dt)` |
| `str(dt)[:N]` | Raw UTC string, no timezone conversion at all. | `_format_utc_as_ist(dt)` or `to_ist(dt)[:N]` |
| `datetime.now(IST_TZ)` | Correct — already tenant timezone. | Leave as-is |
| `eta.strftime(...)` where eta is already IST_TZ | Correct. | Leave as-is |

### Step 3: Fix each path
- API responses (leads, deals, actions, activities) → use `to_ist()`
- Chat/reminder messages → use `_format_utc_as_ist()` for human-readable
- Internal scheduling → leave in UTC (these are for the scheduler, not the user)
- Filenames → leave in UTC (not user-facing)

### Step 4: Verify zero leaks
```bash
grep -n 'isoformat() + .Z' server.py        # Must be empty
grep -n 'created_at\.strftime\|scheduled_at\.strftime\|str(d\.created_at)\[:' server.py  # Must be empty
```

## Key Helpers (server.py)

```python
# Line 17: imported from app.config
from app.config import to_ist, IST_TZ

# Line 3453: local constant
IST_OFFSET = timedelta(hours=5, minutes=30)

# Line 3464: parse IST string → UTC datetime
def _parse_ist_to_utc(dt_val): return dt_val - IST_OFFSET

# Line 3470: format UTC datetime → human-readable IST
def _format_utc_as_ist(dt_val):
    ist_dt = dt_val + IST_OFFSET
    return ist_dt.strftime('%b %d, %I:%M %p IST')
```

## Results (June 17, 2026 audit)

| Leak type | Count found | Count fixed |
|-----------|------------|-------------|
| `.isoformat() + "Z"` | 8 | 8 |
| `.strftime()` on naive UTC | 14 | 14 |
| `str(dt)[:N]` slicing | 2 | 2 |
| Hardcoded +5:30 | 2 | 2 |
| `str(action.due_at)[:19]` in confirmation | 1 | 1 |

Total: 27 leaks, 27 fixes. Zero remaining after audit.

## Pitfall

**Adding `+ "Z"` to `to_ist()` output creates invalid ISO.** `to_ist()` already returns `2026-06-16T09:00:00+05:30`. Appending `"Z"` makes it `2026-06-16T09:00:00+05:30Z` which is syntactically invalid because Z and +05:30 conflict. The JS frontend also had `a.due_at + 'Z'` which broke when the backend started returning proper timezone-aware ISO. Both must be fixed simultaneously.
