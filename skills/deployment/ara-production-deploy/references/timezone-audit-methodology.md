# Timezone Audit Methodology — Full-Stack Pattern

Runs after any datetime-related change to verify consistency across all four layers.

## Audit Commands

### 1. Storage: all datetime creation points (must be UTC)

```bash
# Find all datetime.now() that are NOT UTC
grep -rn "datetime\.now()" server.py app/ | grep -v "utc\|IST\|timezone"
# Every instance should either be utcnow() or datetime.now(timezone.utc)

# Find all naive datetime creation
grep -rn "datetime(" server.py app/ | grep -v "now\|utc\|isoformat\|timezone"
# Should only appear in migrations/test data

# Verify utcnow() returns aware UTC
# database.py: def utcnow(): return datetime.now(timezone.utc)
```

### 2. API Output: every isoformat() must indicate timezone

```bash
# Find all isoformat() calls — everything going to browser/Ava
grep -rn "\.isoformat()" server.py

# Rules:
# - Naive UTC (from SQLite): MUST have + "Z" suffix
# - Aware IST (via to_ist()): already has +05:30 offset → OK
# - Aware UTC (fresh utcnow): isoformat() includes +00:00 → OK
```

### 3. Frontend: every display uses TENANT_TIMEZONE

```bash
# Find all time display points
grep -n "toLocaleString\|toLocaleTime\|toLocaleDate\|toISOString\|slice(0.*16)\|new Date(" static/dashboard.js

# Rules:
# - toLocaleString() MUST have timeZone: TENANT_TIMEZONE
# - toISOString() MUST only be used for data (API calls), never for display
# - datetime-local input: use raw IST string from API, not toISOString() conversion
# - Edit modal save: send raw IST string, let backend convert to UTC
```

### 4. Conversational: every human-facing time is IST

```bash
# Find all time references in system prompts and notifications
grep -n "now_ist\|strftime.*%I\|morning\|afternoon\|evening\|IST" server.py

# Rules:
# - System prompt: "Current time: {now_ist.strftime(...)} (Time of day: {_tod})"
# - Tool results: use eta.strftime('%I:%M %p IST') for human-readable times
# - Notifications: ✨ *Ava :* format with IST times
# - Never say "Good morning" without checking actual time of day
```

## Common Bug Patterns

| Bug | Symptom | Fix |
|-----|---------|-----|
| isoformat() without Z | JS parses as local (IST), shows UTC time | Add `+ "Z"` |
| Frontend toISOString() + backend -5.5h | Double conversion, 11h drift | Remove frontend conversion |
| IST adjustment in scheduler | All backlog fires simultaneously | Use naive UTC comparison |
| datetime-local input with UTC value | Shows wrong time in form | Convert UTC→IST (+330min) |
| Hardcoded "Good morning" | Wrong greeting at 7 PM | Time-aware greeting from _hour |
| Silence engine every 30s | Self-replicating messages | Rate-limit once/day + age gate |

## Post-Fix Verification

```bash
# 1. Check a pending action's due_at display
curl -s http://localhost:8766/api/actions | python3 -c "
import json, sys
d = json.load(sys.stdin)
for a in d.get('actions', []):
    if a.get('status') == 'open' and a.get('due_at'):
        print(a['due_at'])  # Should have Z suffix
        break
"

# 2. Verify no pending ScheduledActions are past-due in UTC
ssh root@HOST 'cd /opt/ara && .../venv/bin/python3 -c "
from datetime import timedelta
from database import init_db, ScheduledAction, utcnow
db = init_db()
now = utcnow().replace(tzinfo=None)
overdue = db.query(ScheduledAction).filter(
    ScheduledAction.status == \"pending\",
    ScheduledAction.scheduled_at <= now - timedelta(hours=1)
).count()
print(f\"Overdue: {overdue}\")  # Should be 0 on fresh deploy
"'

# 3. Verify time of day in system prompt is correct
# Check journal for a recent agent_chat invocation
ssh root@HOST 'journalctl -u ara-server --since "5 minutes ago" | grep "Time of day"'
```
