# Auto-Cadence on Lead Creation — Phantom Outbound (June 15, 2026)

## Bug

When Greg creates a new lead with a phone number but does NOT assign it to Ava (or any agent), an outbound cadence appears to start automatically. When he hits "Pause" and refreshes, the outbound cadence is gone — it was never actually scheduled.

## Root Cause

`create_lead` (server.py ~line 1178) calls `_schedule_cadence_for_lead()` unconditionally for every new lead:

```python
lead = Lead(tenant_id=tenant_id, **data.model_dump())
lead.cadence_type = determine_cadence(data_dict.get("lead_source", "form"), lead_stage)
lead.cadence_auto_assigned = 'yes'
# ... db commit ...
_schedule_cadence_for_lead(lead, db)  # ← triggers even without assigned_agent
```

The UI state showed "outbound running" because the cadence fields (`cadence_type`, `cadence_auto_assigned`) were set, but the actual scheduling may have failed silently or produced phantom ScheduledActions.

## Fix

```python
# Only schedule if an agent is assigned
if lead.assigned_agent:
    try:
        _schedule_cadence_for_lead(lead, db)
    except Exception as e:
        logging.getLogger("scheduler").warning(f"Failed to schedule cadence: {e}")
```

## User Expectation

Greg's expectation is correct: unless he explicitly triggers an outbound campaign (by assigning a lead to Ava), nothing should fire. Auto-cadence should only happen for agent-assigned leads.
