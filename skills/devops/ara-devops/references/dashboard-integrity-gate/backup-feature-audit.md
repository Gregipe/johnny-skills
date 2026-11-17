# Backup Feature Audit — Detecting Silent Regression

When a function in `dashboard.js` is rewritten (e.g., `showAddDealModal`), the new version can silently drop features from the old version. The user notices immediately: *"Why are features missing in the codebase?"*

## The audit technique

Compare the current file against the most recent backup using keyword frequency:

```python
#!/usr/bin/env python3
"""Audit dashboard.js against a known-good backup."""
keywords = [
    '_fillDealLead', '_hideDealDrop', '_hideMenus', '_stripActionPrefix',
    'deleteActionItem', 'editActionItem', 'saveEditedAction', 'renderUnifiedTab',
    'attachAMDropdowns', 'addDealLeadPicker', 'addDealContactName',
    'addDealContactDetails', 'addDealContactInfo', 'addDealLeadId',
    'addDealDesignation', 'am-edit', 'am-done', 'am-delete', 'am-toggle',
    'am-container', 'am-dropdown', 'data-aid', 'function editAction(',
    'function deleteAction(', '_selectedActions', '_bulkBar',
]

with open('/opt/ara/static/dashboard.js') as f:
    curr = f.read()
with open('/opt/ara/static/dashboard.js.bak.YYYYMMDD_HHMMSS') as f:
    old = f.read()

for kw in keywords:
    c1 = old.count(kw)
    c2 = curr.count(kw)
    if c1 > 0 and c2 == 0:
        print(f"MISSING: {kw} (was {c1}, now 0)")
```

## When to run

1. After any deploy that rewrites a function with >50 lines changed
2. When the user reports a feature that "used to work"
3. As a post-deploy gate alongside `dashboard_integrity_test.py`

## Case study: June 20, 2026 regression

Between 10:27 and 12:49 on June 20, `showAddDealModal` was rewritten. The new version dropped:

| Feature | Impact |
|---------|--------|
| `_fillDealLead` | Deal modal lead picker auto-fill broken |
| `addDealLeadPicker` + dropdown | Contact Person became plain text input |
| `_stripActionPrefix` | `action_` prefix 404s on edit/delete |
| `editActionItem` | Lost Owner and Channel dropdowns in edit modal |
| `saveEditedAction` | Lost proper PATCH with all fields |
| `deleteActionItem` | Lost prefix-stripping delete |

Total: 16,406 bytes removed, 282 lines deleted, 8 functions lost.

## Pitfall

Keyword counting can show false positives if a function was intentionally renamed. Always verify each MISSING entry by reading the old code to understand what it did — don't blindly restore.
