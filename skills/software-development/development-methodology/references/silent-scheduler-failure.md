# Silent Scheduler Failure Pattern

## The Bug

The ARA scheduler (`_run_scheduler` in `server.py`) can fail silently in two ways, both caused by datetime comparison issues:

### Pattern 1: Offset-aware vs offset-naive TypeError

**Root cause:** `utcnow()` returns `datetime.now(timezone.utc)` (aware), but `scheduled_at` in the DB is stored as naive `datetime` (no timezone info). Python raises `TypeError: can't compare offset-naive and offset-aware datetimes`.

**Why it's silent:** The scheduler wraps everything in:
```python
try:
    db = init_db()
    try:
        # ... comparison throws TypeError
    except Exception:
        db.close()
except Exception:
    pass
time.sleep(30)
```

The bare `except Exception` catches the TypeError, and the scheduler just sleeps and retries — every 30 seconds, forever. Zero log output, zero alerts, zero notifications delivered.

**Fix:** Use `utcnow().replace(tzinfo=None)` — naive UTC.

### Pattern 2: IST/UTC timezone mismatch (string comparison)

**Root cause:** After fixing Pattern 1, the scheduler still fails silently because `scheduled_at` is stored as IST datetime strings (e.g., `"2026-06-15 18:00:00"` IST), but `now` is UTC (e.g., `"2026-06-15 12:30:00"` UTC). String comparison: `"18:00"` > `"12:30"` → `False`. No events ever match.

**Why it's silent:** No error — the comparison just returns empty results. The scheduler polls, finds nothing due, sleeps, repeats.

**Fix:** Convert `now` from UTC to IST before comparing: `(now + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")`. SQLAlchemy compares DateTime column with string, SQLite does string comparison — which is chronologically correct for ISO timestamp strings.

## Detection

```bash
# Check if any pending ScheduledActions should have fired by now
ssh host 'cd /opt/ara && python3 -c "
from database import init_db, ScheduledAction
from datetime import datetime, timezone, timedelta
db = init_db()
now = datetime.now(timezone.utc)
ist_now = now + timedelta(hours=5, minutes=30)
pending = db.query(ScheduledAction).filter(
    ScheduledAction.status == \"pending\",
    ScheduledAction.scheduled_at <= ist_now.replace(tzinfo=None)
).all()
print(f\"{len(pending)} overdue pending ScheduledActions\")
for s in pending:
    print(f\"  {s.id}: {s.action_type} scheduled_at={s.scheduled_at} (now IST={ist_now})\")
db.close()
"'
```

If overdue pending actions exist and no WhatsApp was received → scheduler is broken.

## Prevention

1. **Never use bare `except Exception:` in scheduler loops.** At minimum, log the exception:
   ```python
   except Exception as e:
       logger.error(f"Scheduler tick failed: {e}", exc_info=True)
   ```

2. **Always check `scheduled_at` timezone.** Find every `ScheduledAction` creation point and verify what timezone the datetime is in. Store as UTC or IST consistently, and compare consistently.

3. **Healthcheck should detect overdue actions.** Add to `ara-server-healthcheck`: after restart, query for pending ScheduledActions that should have fired. Alert if any exist.

4. **Monitor for zero-activity.** A scheduler delivering zero notifications for days is itself a loud signal. A periodic healthcheck ping that expects a response on WhatsApp would catch this.
