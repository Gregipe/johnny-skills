# Daily Owner Catch-Up Cron (June 2026)

## Overview
A daily 6:30 PM IST summary sent to the owner's WhatsApp. Covers today's completed actions, pending action items, and unresolved watchlist items. Runs inside the ARA scheduler loop (not a separate process).

## Implementation

### Function: `_send_daily_summary()` (server.py ~line 7416)
```python
_last_summary_date = None  # module-level sentinel

def _send_daily_summary():
    global _last_summary_date
    now_ist = utcnow() + _td(hours=5, minutes=30)
    
    # Fire window: 6:30 PM - 7:30 PM IST, once per day
    if not (18 <= now_ist.hour < 19 and now_ist.hour == 18 and now_ist.minute >= 30):
        return  # not in fire window
    
    today = now_ist.date()
    if _last_summary_date == today:
        return  # already sent today
    
    # Gather data
    completed = db.query(ScheduledAction).filter(
        ScheduledAction.tenant_id == TENANT_ID,
        ScheduledAction.status == "completed",
        ScheduledAction.fired_at >= (utcnow() - _td(hours=24)),
    ).count()
    
    action_items = db.query(ActionItem).filter(
        ActionItem.tenant_id == TENANT_ID,
        ActionItem.status == "open",
    ).all()
    
    watchlist = db.query(AvaWatchlist).filter(
        AvaWatchlist.tenant_id == TENANT_ID,
        AvaWatchlist.resolved == False,
    ).all()
    
    # Send via WhatsApp to owner
    wa.send_to_jid(owner_jid, message)
    _last_summary_date = today
```

### Integration in Scheduler Loop
In `_run_scheduler()`, called once per loop iteration:
```python
try:
    _send_daily_summary()
except Exception:
    pass
```

### Key Design Decisions
- **Single-fire sentinel**: `_last_summary_date` global prevents duplicate sends if the scheduler runs multiple times in the firing window.
- **IST timezone**: Uses `utcnow() + timedelta(hours=5, minutes=30)` for IST comparison. The 30-minute window (6:30-7:30 PM) prevents off-by-one errors.
- **No DB state tracking**: The sentinel resets on server restart. If the server restarts between 6:30-7:30 PM, the summary fires once. Acceptable trade-off.
- **Exception-wrapped**: The scheduler loop catches all exceptions so a failed summary doesn't break the scheduler.
- **WhatsApp delivery**: Uses `wa.send_to_jid()` to send directly to the owner. The message includes: today's completed actions, open action items, unresolved watchlist items.

### Pitfalls
- **IST = UTC + 5:30**. Always compute IST from UTC, not from `datetime.now()` (which is local time on the server).
- **The sentinel is per-process**. If multiple ARA instances run, each sends independently. Singleton architecture makes this fine.
- **Test by temporarily lowering the hour check** to current time + 5 minutes. Don't forget to restore.
