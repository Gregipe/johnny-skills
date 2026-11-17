# IST/UTC Timezone Centralization

## Pattern

Replace ad-hoc `timedelta(hours=5, minutes=30)` and `IST_OFFSET` with three central functions in `app/config.py`:

```python
from datetime import timedelta as _IST_TD

def ist_to_utc(dt):
    """Convert IST datetime to UTC. dt should be a naive datetime assumed to be IST."""
    if dt is None: return None
    return dt - _IST_TD

def utc_to_ist(dt):
    """Convert UTC datetime to IST."""
    if dt is None: return None
    return dt + _IST_TD

def parse_due_at(due_str):
    """Parse ISO datetime string, treat it as IST, convert to UTC.
    Date-only strings default to 18:00 IST (end of business day)."""
    if not due_str: return None
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(due_str)
        if len(due_str) <= 10:  # date-only
            dt = dt.replace(hour=18, minute=0, second=0, microsecond=0)
        return ist_to_utc(dt)
    except (ValueError, TypeError):
        return None
```

## Usage

```python
from app.config import ist_to_utc, utc_to_ist, parse_due_at

# Before (fragile):
due_at = due_at - timedelta(hours=5, minutes=30)  # IST→UTC
due = due - IST_OFFSET  # IST→UTC (duplicate!)
if len(due_at_str) > 10: due = due - IST_OFFSET  # BUG: skips date-only

# After (one truth):
action.due_at = ist_to_utc(action.due_at)
due = parse_due_at(due_at_str)
```

## Bugs Caught

### 1. create_action_item date-only skip
```python
# ❌ OLD — date-only strings skipped conversion entirely
if len(due_at_str) > 10:
    due = due - IST_OFFSET

# ✅ FIXED — parse_due_at handles both cases
due = parse_due_at(due_at_str)
```

### 2. set_cron uses UTC clock as IST
```python
# ❌ OLD — utcnow().replace(hour=IST_HOUR) treated UTC as IST
first_at = utcnow().replace(hour=hour, minute=minute)

# ✅ FIXED — convert through IST timezone
ist_now = utc_to_ist(utcnow())
first_at = ist_now.replace(hour=hour, minute=minute)
first_at = ist_to_utc(first_at)
```

## Verification

All API endpoints returning dates must include `+05:30` suffix. Check with:
```python
curl -s http://localhost:8766/api/actions?limit=1 | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(d['actions'][0]['due_at'])"
# Should show: 2026-06-23T11:30:00+05:30
```

## Test

`test_baileys_init.py` validates WhatsApp client init (including timezone-dependent attributes).
