# SQLite: Fingerprinting Unexplainable DB State

## The Problem

You discover rows in a SQLite database with values that don't make sense — e.g., `execution_state = "completed"` when no code in the codebase ever sets that value. SQLite has no row modification timestamps, no audit trail, and no change tracking. You need to determine: did the application do this, or was it direct DB manipulation?

## The Fingerprinting Technique

**Core principle:** Search the entire codebase AND git history for the exact suspicious value. If it doesn't appear as a SET operation anywhere, it's direct DB manipulation — the value is a human-chosen word, not a system-generated one.

### Step 1: Find every place the field is SET

```bash
# Search codebase for all assignments to the field
grep -rn '\.execution_state\s*=' server.py database.py 2>/dev/null | grep -v 'cf_log\|#\|comment\|!=\|notin_'

# Search git history for the same pattern
git log --all -p --since='DATE' -- server.py | grep -i '"completed"\|execution_state.*completed'
```

This tells you what values the application CAN set. Make a list.

### Step 2: Check if the suspicious value is in the list

If `execution_state = "completed"` appears nowhere in the allowed-values list, it was set externally. The value itself is the fingerprint — a human chose "completed" as a word, but the system only uses `pending`, `awaiting_approval`, `fired`, `cancelled`.

### Step 3: Correlate with server restarts (if available)

```bash
# Check process restarts around the time window
journalctl -u SERVICE --since='START_TIME' --until='END_TIME' --no-pager | grep -i 'Started\|Listening\|ready'
```

Multiple PID changes in a short window suggest frequent restarts, which can correlate with startup scripts or manual intervention.

### Step 4: Search for migration/cleanup scripts

```bash
# Look for one-off scripts in /tmp or project root
ls -la /tmp/*.py 2>/dev/null | head -20
ls -la *.py fix*.py sync*.py migrate*.py 2>/dev/null

# Check git log for commit messages mentioning DB fixes
git log --oneline --all | grep -i 'fix.*row\|sync\|db.*row\|manual'
```

### Step 5: Search for agent/tool calls that could set the field

```bash
# Check agent chat logs for the suspicious action IDs
python3 -c "
import sqlite3
db = sqlite3.connect('ara.db')
msgs = db.execute('''SELECT created_at, substr(content,1,400) FROM agent_chat_messages
    WHERE content LIKE '%update_action%' AND content LIKE '%outcome_state%'
    ORDER BY created_at DESC LIMIT 20''').fetchall()
for m in msgs:
    print(f'[{m[0][:19]}] {m[1][:200]}')
"
```

## When to Stop

You've exhausted all code paths, git history, logs, and scripts. The suspicious value doesn't appear as a SET anywhere. At this point, conclude: **direct DB manipulation** — either a manual SQL UPDATE or an external script. You cannot determine the exact cause without row-level timestamps.

## Real Case (ARA, June 2026)

Three `action_type=manual` ActionItems had `execution_state="completed"` and `outcome_state="resolved"`. The value `"completed"` did not exist in any code path. Ruled out: `_prune_pending_actions` (only touches `awaiting_approval`), confirmation flow (only fires for `pending_confirmation` type), `update_action` tool (no log of outcome_state args), git history (no commit adds "completed" to execution_state). Concluded: direct DB manipulation. Could not determine who/when due to SQLite's lack of row timestamps.

## Prevention

- Add an `action_items_snapshot` table with `snapshot_at` timestamp, populated before state changes
- Consider hourly JSON dumps of critical tables for disaster recovery
- If row modification timestamps matter, consider a database that supports them (PostgreSQL `updated_at` triggers)
