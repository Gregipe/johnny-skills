# IST/UTC Timezone Normalization Bug

**Root cause:** ARA stored `scheduled_at` in three different timezone conventions (IST naive, UTC aware, UTC naive) and the scheduler compared them using a mix of approachable datatypes. This caused:
1. Zero notifications ever delivered (weeks of silent failure)
2. 12 back-to-back messages at once (burst fire after "fix")

## The Two-Layer Bug

### Layer 1: Silent TypeError (Original Bug)
```python
# scheduler _run_scheduler
now = utcnow()  # aware UTC: 2026-06-15 12:30:00+00:00
due = db.query(ScheduledAction).filter(
    ScheduledAction.scheduled_at <= now  # naive stored: 2026-06-15 18:00:00
)
```

`TypeError: can't compare offset-aware and offset-naive datetimes` — caught by bare `except Exception:` → scheduler slept 30s → repeat forever. **Zero events ever fired.**

### Layer 2: IST Adjustment Burst (First "Fix")
```python
# Broken fix: convert UTC now to IST string
now_ist_str = (now + timedelta(hours=5, minutes=30)).strftime(...)
# Cadence stores UTC: 14:10 UTC = "2026-06-15 14:10:26"
# String compare: "14:10" <= "18:51" → TRUE → fires immediately!
```

The IST string comparison treated UTC-stored cadence dates as IST strings, making them appear 5.5 hours early. All cadence steps with similar `scheduled_at` fired simultaneously.

### The Fix: Normalize Everything to UTC

**Storage:** All `scheduled_at` values stored as naive UTC.
```python
# POST/PATCH /api/actions — convert IST user input → UTC
due_at = datetime.fromisoformat(raw_due)
due_at = due_at - timedelta(hours=5, minutes=30)  # IST → UTC
```

**Scheduler:** Compare naive UTC against naive UTC.
```python
now = utcnow().replace(tzinfo=None)  # naive UTC
scheduled_at <= now  # both naive UTC strings
```

**Display:** Convert UTC → IST for datetime-local inputs.
```javascript
// Edit modal — UTC stored → IST for datetime-local
var dueStr = a.due_at
  ? new Date(new Date(a.due_at).getTime() + 330*60*1000).toISOString().slice(0, 16)
  : '';
```

**Table display:** Uses `toLocaleString({timeZone: TENANT_TIMEZONE})` — automatic conversion.

## Cadence Already Stores UTC

The cadence module (`app/services/cadence.py`) uses `utcnow()` for `scheduled_at`, so cadence dates were already UTC. The dashboard actions were the ones storing IST.

## Verification

After fix, all creation points store UTC:
- `POST /api/actions` → `due_at - 5.5h`
- `PATCH /api/actions` → `due_at - 5.5h`
- Cadence → `utcnow()` (already UTC)
- `set_reminder` / `create_action_item` → `utcnow()` (already UTC)

Scheduler compares UTC → UTC. No timezone conversion in the comparison path.
