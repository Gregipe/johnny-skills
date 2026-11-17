# ActionItem ref_type/ref_id (NOT lead_id) Pitfall

## The Bug

Multiple code paths in server.py referenced `a.lead_id` on ActionItem objects, but ActionItem has NO `lead_id` column. It uses `ref_type` (e.g., "lead") and `ref_id` instead.

```python
# BROKEN — ActionItem has no lead_id column
if a.lead_id:
    lead = db.query(Lead).filter(Lead.id == a.lead_id).first()

# CORRECT — use ref_type + ref_id
if a.ref_type == "lead" and a.ref_id:
    lead = db.query(Lead).filter(Lead.id == a.ref_id).first()
```

## Affected Code Paths

This was fixed in three places on June 16, 2026:
1. `/api/action-items` endpoint
2. `get_action_items` agent-chat tool handler
3. Morning briefing (`__morning_briefing__`) generation

## Verification

```bash
# Verify no remaining lead_id references on ActionItem
grep -n "\.lead_id" /opt/ara/server.py | grep -i "action\|_a\."
```
