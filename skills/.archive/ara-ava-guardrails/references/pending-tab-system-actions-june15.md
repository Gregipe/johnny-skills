# Pending Tab — System Actions Visibility Fix (June 15, 2026)

## The Bug

The Pending tab on the unified Actions page used `/api/actions` (ActionItem endpoint, line 2642 in server.py). This endpoint had a filter:

```python
q = db.query(ActionItem).filter(
    ActionItem.tenant_id == TENANT_ID,
    ActionItem.ref_type == "lead"  # ← EXCLUDED system actions
)
```

Actions created without a lead (from the navbar "+ New Action" with lead left blank) had `ref_type=null`, so they were excluded from the Pending tab even though they appeared in the History tab and on the API response when queried directly.

## The Fix

Removed the `ref_type == "lead"` filter. The endpoint now shows ALL ActionItems for the tenant:

```python
q = db.query(ActionItem).filter(
    ActionItem.tenant_id == TENANT_ID,
    # No ref_type filter — show system + lead actions
)
```

Also fixed the `leads_map` lookup to handle `None` ref_id:

```python
"lead_name": (leads_map.get(a.ref_id) or Lead()).name if a.ref_id else "",
```

## Verification

- System actions (no lead) appear in Pending tab with "—" in the Lead column
- Lead-scoped actions show the lead name as a clickable link
- API returns `lead_id=null, lead_name=""` for system actions — frontend renders "—"
