# Feature Regression Audit

When dashboard.js (or any large JS file) has a feature regression — something that used to work no longer does — don't guess. Compare backups systematically to find exactly what was lost.

## When to Use

- User reports a feature that "used to work" is now missing
- After reverting to a backup (features may have been added after that backup)
- After a sprint deploy that touched the same file
- When code size drops significantly between versions (16KB in the June 20 case)

## Step 1: Identify the Window

Find the last backup where the feature existed and the first where it's missing:

```bash
# Check keyword presence across backups
for backup in /opt/ara/static/dashboard.js.bak.*; do
  echo "$(basename $backup): $(grep -c 'FEATURE_KEYWORD' $backup)"
done
```

This gives you the exact time window when the feature was lost.

## Step 2: Function-Level Diff

Find which functions were removed:

```bash
diff \
  <(grep -oP 'function \w+|window\.\w+\s*=\s*function' BACKUP_OLD | sort -u) \
  <(grep -oP 'function \w+|window\.\w+\s*=\s*function' BACKUP_NEW | sort -u) \
  | grep '^<'
```

Lines starting with `<` are functions that existed in the old version but NOT in the new one.

## Step 3: Keyword Audit

Use a Python script to compare keyword counts between versions:

```python
keywords = [
    'function_name', 'variable_name', 'html-id', 'css-class',
    'api-endpoint-pattern', 'event-handler-pattern'
]
for kw in keywords:
    c1 = old_content.count(kw)
    c2 = new_content.count(kw)
    if c1 > 0 and c2 == 0:
        print(f"LOST: {kw} ({c1} refs removed)")
```

Common keywords to check for regressions:
- Function names: `editActionItem`, `deleteActionItem`, `_fillDealLead`, etc.
- HTML IDs: `addDealLeadPicker`, `addDealContactInfo`, etc.
- CSS classes: `am-edit`, `am-toggle`, `data-aid`, etc.
- API calls: `/api/leads/search`, `/api/actions/`, etc.

## Step 4: Dangling Reference Check

Find code that references removed functions — these cause runtime errors:

```python
# Check if the NEW version still calls functions that were removed
for fn in REMOVED_FUNCTIONS:
    count = new_content.count(fn)
    if count > 0:
        print(f"DANGLING: {fn} called {count} times but not defined")
```

Dangling references cause two types of failures:
- **In IIFE scope (dashboard.js):** The entire IIFE fails to execute → page is blank/frozen
- **In onclick handlers:** Button renders but clicking does nothing (silent failure)

## Step 5: Event Handler Audit

Check if event delegation handlers for UI elements still exist:

```python
# Check for am-* system
print("Has am-* click delegation:", 'closest(".am-' in content)
print("am-* HTML elements:", content.count('am-toggle'))
print("am-* handler references:", content.count('editActionItem'))
```

A mismatch (HTML elements exist but no handler, or handler exists but no HTML) = broken UI.

## Step 6: Escape Corruption Check

Shell pipes can mangle JavaScript escaping without breaking `node -c`:

```python
# These patterns indicate shell pipe corruption
print("Triple-backslash:", content.count('\\\\\\\\\\"'))
print("Double-escaped quotes in JS string:", content.count('class=\\\\\\"'))
```

`node -c` cannot detect escape corruption — only the browser catches `Invalid escape in identifier`. Always run `dashboard_integrity_test.py` which checks the served file.

## Step 7: Restore from Backup

Once you know exactly what's missing and the backup version has clean code:

1. Extract the exact line range from the backup
2. Verify the extracted code doesn't reference other missing functions
3. Check for function name conflicts with current code
4. Apply via `safe_write.py`
5. Run `dashboard_integrity_test.py`
6. Bump version, restart, smoke test

**Pitfall:** Don't restore entire functions blindly — the backup might itself have bugs (e.g., `attachAMDropdowns` was called but never defined). Extract only what's needed.

## Real Example: June 20 Regression

Between Jun 20 10:27 and 12:49, 16,406 bytes (282 lines) were removed from dashboard.js. The audit found:

| Lost Feature | Lines | Impact |
|-------------|-------|--------|
| am-* event delegation handler | ~42 | ⋮ dropdowns stopped working |
| `_stripActionPrefix()` | 4 | `action_` prefix → 404 on edit/delete |
| `editActionItem()` | ~60 | Lost Owner/Channel dropdowns in edit modal |
| `saveEditedAction()` | ~40 | Lost full PATCH with all fields |
| `deleteActionItem()` | ~15 | Lost prefix stripping on delete |
| `_fillDealLead()` | ~40 | Deal lead picker broken |
| `renderUnifiedTab()` | ~90 | Replaced by separate render functions |

Root cause: A sprint agent bulk-rewrote `showAddDealModal` and accidentally removed interleaved functions. The 12:49 version passed `node -c` (no syntax errors) but had zero action editing/deleting mechanisms.
