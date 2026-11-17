# Dashboard.js Backup Restoration Checklist

**Never restore a backup blindly.** Always diff first.

## Before Restoring

```bash
# 1. Count feature signatures in current (corrupted) vs backup
diff <(grep -c 'overdue\|isOverdue' current.js) <(grep -c 'overdue\|isOverdue' backup.js)
diff <(grep -c 'renderHistoryTab' current.js) <(grep -c 'renderHistoryTab' backup.js)

# 2. Check for any removed functions
diff <(grep -oP 'function \w+' current.js | sort -u) <(grep -oP 'function \w+' backup.js | sort -u)

# 3. Check file size delta
echo "Current: $(wc -c < current.js) | Backup: $(wc -c < backup.js)"
```

## Feature Checklist

Before accepting a backup restore, verify these features exist in the backup:

- [ ] Deal lead picker (`addDealLeadPicker`, `_fillDealLead`, autocomplete dropdown, readonly email/phone)
- [ ] Overdue detection in actions table (`isOverdue`, `stateLabel === 'Overdue'`)
- [ ] History tab fetches resolved/dismissed items (`?status=resolved`, `?status=dismissed`)
- [ ] Sort functions (if recently added)
- [ ] Lead view filter (`action_type != 'pending_confirmation'`)
- [ ] Three-dot menu `position:fixed` (if recently applied)
- [ ] Any sprint-specific features added in the last 2 sprints

## Tracing a Feature Regression Across Backups

When a feature is discovered missing and the timeline is unknown, scan all timestamped backups to find the exact window:

```bash
# Find which backups have the feature signature and which don't
for f in /opt/ara/static/dashboard.js.bak.*; do
  echo "$(basename $f): $(grep -c 'FeatureSignature' $f) occurrences"
done
```

Example output from June 2026 lead picker regression:
```
dashboard.js.bak.20260615_160403: 6   ← feature present
dashboard.js.bak.20260620_102723: 6   ← feature present
dashboard.js.bak.20260620_124925: 0   ← feature GONE (lost between 10:27 and 12:49)
dashboard.js.bak.20260620_164610: 0
dashboard.js.bak.20260620_174155: 0
```

This narrows the regression to a specific time window. Restore from the LAST backup that still has the feature.

Common feature signatures to grep for:
- `addDealLeadPicker` — deal creation lead autocomplete
- `_fillDealLead` — lead-to-deal field inheritance
- `setupLeadAutocomplete` — reusable lead search component
- `isOverdue` — overdue detection logic
- `renderHistoryTab` — history tab rendering

## If Features Will Be Lost

Don't revert. Instead:

1. Extract the feature code from the corrupted version
2. Restore the backup
3. Re-apply the feature with `safe_write.py`

## Post-Restore Verification

```bash
# Always run after ANY restore
python3 dashboard_integrity_test.py
python3 test_action_item_drift.py
python3 t2_agreement.py
```
