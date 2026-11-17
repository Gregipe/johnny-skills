# Action Notification Engine Architecture

Implemented June 14, 2026. Three-channel notification system for ARA's Actions Platform.

## Trigger Points

Every 30 seconds in `_run_scheduler()`, the `_check_action_notifications()` function runs:

1. **Due-soon / overdue human actions**: Owned by human, not resolved, due within 2 hours or overdue → alerts Greg
2. **Ava-gated approvals**: Owned by Ava, requires_confirmation=True, pending → alerts Greg

## Data Flow

```
ActionItem (DB) → _check_action_notifications() → alerts[] → 
  ├─ _notify_owner(channel="whatsapp") → wa.send_message_sync(admin.phone, text)
  ├─ _notify_owner(channel="email")    → send_via_gmail_api(tokens, admin.email, subject, body)
  └─ LearningNotification(notif_type="action_reminder") → Dashboard "system jobs" view
```

## Deduplication

Each action gets ONE notification per day. Tracked via `LearningNotification` entries with `notif_type="action_reminder"` and `ref_id=action_id`. Before creating a new notification, the function checks if a `LearningNotification` already exists for that action_id today.

## Email Path

Uses the existing Gmail OAuth integration — fetches tokens from `IntegrationConfig` where `integration_id="email-gmail"` and `enabled=True`. Calls `send_via_gmail_api()` which auto-refreshes tokens on 401.

## Pitfalls Fixed

1. **SQL NULL**: `outcome_state != "resolved"` excluded NULL rows. Fixed with `or_(outcome_state != "resolved", outcome_state.is_(None))`.
2. **String due_at**: SQLite stores due_at as string `"2026-06-14 11:30:00"` (space separator). Fixed with `strptime(due_dt, "%Y-%m-%d %H:%M:%S")` fallback after `fromisoformat()` fails.
3. **logger.error Format**: The logger's format string includes `%(request_id)s` which isn't available in the scheduler daemon thread. Fixed by using `print()` instead.
4. **due_at[:10] TypeError**: After parsing due_at from string to datetime, slicing `[:10]` fails. Fixed with `str(a.due_at)[:16]` (shows date + time).

## Scheduler Integration

```python
# In _run_scheduler() loop, after existing checks:
try:
    _check_action_notifications()
except Exception:
    pass  # Don't crash the scheduler for notification failures
```

The `except: pass` prevents notification failures from bringing down the scheduler, but also makes failures silent. Use `print(f"⚠️ Action notifications: {e}", flush=True)` inside the function for visibility in systemd logs.
