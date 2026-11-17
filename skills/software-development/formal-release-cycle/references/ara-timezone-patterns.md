# ARA Timezone Patterns

## BINDING RULE: Centralized conversion only

ARA handles IST (UTC+5:30) as the user timezone. ALL date/time values are stored in UTC in the database. Every conversion between IST and UTC MUST use the three centralized functions in `app/config.py`:

```python
ist_to_utc(dt)    # IST → UTC: subtracts 5:30
utc_to_ist(dt)    # UTC → IST: adds 5:30
parse_due_at(str) # Parses ISO string, defaults date-only to 18:00 IST, converts to UTC
```

## NEVER DO THIS (21 sites were fixed June 23, 2026)

```python
# BANNED — ad-hoc conversion. Will drift. Will be forgotten.
due_at = due_at - timedelta(hours=5, minutes=30)
due = due - IST_OFFSET
ist_dt = dt_val + IST_OFFSET

# CORRECT — centralized, grep-able, single source of truth
due_at = ist_to_utc(due_at)
ist_dt = utc_to_ist(dt_val)
due = parse_due_at(due_at_str)
```

## Pitfalls that caused production bugs

### 1. Date-only strings skip conversion
The `create_action_item` tool had `if len(due_at_str) > 10` guard that skipped IST→UTC for date-only strings like `"2026-06-23"`. The datetime was stored as midnight UTC instead of 18:30 UTC (previous day). **Fix:** Use `parse_due_at()` which handles both date-only and datetime strings consistently.

### 2. UTC clock used as IST
The `set_cron` tool did `utcnow().replace(hour=ist_hour)` — treating a UTC timestamp as IST. ScheduledActions fired 5.5 hours early. **Fix:** Convert via `ist_to_utc(ist_now.replace(...))`.

### 3. Batch SA creation with utcnow()
When multiple ScheduledActions were created in one tick for past-due actions, they all got `scheduled_at = utcnow()` — firing immediately and bombarding the user. **Fix:** Blast guard in `_execute_action` suppresses >3 `whatsapp_to_owner` fires in a 60-second window.

### 4. PATCH endpoint didn't sync SAs
Editing an action's `due_at` via the dashboard updated the ActionItem but never created/updated the ScheduledAction. Reminders silently dropped. **Fix:** PATCH endpoint now creates/updates/cancels SAs when `due_at` changes.

## Test verification checklist

When deploying any change touching dates/times:
1. Run IST verification test: all API responses show `+05:30` timezone suffix
2. No UTC midnight hours (0:00-4:30) in displayed dates
3. PATCH a due_at → verify ScheduledAction created with correct `scheduled_at`
4. set_cron → verify first_at is 5:30 behind the IST time (converted to UTC)
5. create_action_item with date-only → verify it's 18:30 UTC (midnight IST next day minus 5:30)

## History

- June 23, 2026: Replaced 21 ad-hoc conversion sites with centralized functions. Fixed 4 timezone bugs that caused WhatsApp reminders to fire at 6 AM IST instead of intended times.
