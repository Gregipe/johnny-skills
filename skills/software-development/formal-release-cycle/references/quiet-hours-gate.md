# Periodic Notification Checks — Quiet-Hours Gate

## The Bug
`_check_action_notifications()` runs every 30 seconds and sends WhatsApp + email reminders for overdue/near-due action items. The dedup window resets at midnight IST (`today_start`), so at 00:00 IST ALL past-due items trigger fresh notifications — waking Greg up at midnight.

## The Fix
Add a quiet-hours gate at the TOP of any periodic check that sends notifications:

```python
# Suppress during sleeping hours (10 PM - 7 AM IST)
hour = ist_now.hour
if hour < 7 or hour >= 22:
    return  # silently skip
```

## Pattern
Any periodic function that sends user-facing notifications MUST:
1. Gate by time-of-day (quiet hours: 10 PM - 7 AM local time)
2. Deduplicate within a window (today_start for daily, or 4-hour if more frequent)
3. NOT fire immediately after the dedup window resets — wait until waking hours

## Audit Checklist
- [ ] Every periodic notification sender has a `hour` gate
- [ ] Dedup windows don't reset during sleeping hours
- [ ] No notification can fire at midnight
