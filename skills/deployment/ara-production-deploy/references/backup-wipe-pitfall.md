# Backup-Wipe Pitfall (June 2026)

## The Pattern

When debugging on the production server:

```bash
# Step 1: Apply fix A → works, but don't commit yet
ssh root@HOST 'cd /opt/ara && cp server.py /tmp/server.py.bak.FIX_A'

# Step 2: Apply fix B → syntax error! Server crashes.
# "Quick, restore from earlier backup!"

ssh root@HOST 'cd /opt/ara && cp /tmp/server.py.bak.FIX_A server.py'
systemctl restart ara-server
```

**Fix A is now GONE — wiped by the restore.**

## Root Cause

Blind restores from a timestamped backup overwrite ALL changes made between the backup timestamp and the restore, including working fixes. The backup is a point-in-time snapshot with no knowledge of subsequent edits.

## Real Session Impact (June 15, 2026)

Three separate fixes were applied to `server.py` in a single session:
1. `due_at` string → datetime parsing in `create_action` handler
2. Route rename: `GET /api/actions/{id}` → `GET /api/leads/{id}/actions`
3. `action_type="manual"` added to `create_action` handler

A logging change introduced a syntax error. Restoring from `server.py.bak.20260615_160022` wiped ALL THREE fixes. Fix #1 was re-applied, but fixes #2 and #3 were NOT noticed as missing until Greg reported:
- Lead detail page showing zero actions (route rename was wiped, frontend called wrong URL)
- `create_action` still crashing with NOT NULL constraint (action_type fix was wiped)

## Prevention

### 1. Commit after every working fix — don't stack uncommitted fixes
```bash
# ✅ After each fix:
ssh root@HOST 'cd /opt/ara && git add server.py && git commit -m "fix: description" && git push origin main'
```

### 2. If you must stack: verify ALL deployed fixes survive after a restore
```bash
# After restore, re-check every earlier fix
grep 'new pattern from fix 1' /opt/ara/server.py
grep 'new route from fix 2' /opt/ara/server.py
grep 'new field from fix 3' /opt/ara/server.py
```

### 3. Use `git stash` + `git pull --rebase` instead of file-level backups
```bash
# ✅ Safer than cp backup:
ssh root@HOST 'cd /opt/ara && git stash && git pull origin main && git stash pop'
# If stash fails or conflicts, you can inspect before applying
```

### 4. Targeted patches instead of full-file backups
```bash
# ✅ Backup only the lines you're changing:
ssh root@HOST 'cd /opt/ara && sed -n "3489,3510p" server.py > /tmp/fix_context.bak'
# Restore is targeted, not a full file overwrite
```

## Detection Checklist

After any production restore:
- [ ] Re-verify all fixes that were applied BEFORE the backup was taken
- [ ] Check frontend still calls correct backend URLs (route renames survive)
- [ ] Check DB constraints are satisfied (new required fields survive)
- [ ] Check all tool handlers are functional (type conversions survive)
- [ ] Run the test suite (catches missing fixes)
