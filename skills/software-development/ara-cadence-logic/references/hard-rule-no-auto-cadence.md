# ⛔ HARD RULE: No Auto-Cadence

**Cadence MUST NEVER auto-schedule on lead creation or CSV import.** Non-negotiable.

This rule was established June 15, 2026 after 12 back-to-back WhatsApp/email messages were sent to a live lead (Prashant Rai) who wasn't even assigned to Ava.

## What Was Removed

- `create_lead()` (server.py:1177-1182) — `_schedule_cadence_for_lead()` call removed
- `upload_leads_csv()` (server.py:1583-1595) — entire auto-schedule loop removed

## How Cadence Can Be Triggered

Cadence ONLY triggers via:
1. Explicit API call: `POST /api/tenants/{tenant_id}/leads/{lead_id}/cadence`
2. Explicit tool call: `schedule_cadence` from agent/coaching flow
3. Manual UI action: user clicks "Start Cadence" on a lead

## Code State After Fix

```python
# server.py — create_lead()
db.commit()
# Cadence is NEVER auto-scheduled. Only triggered via explicit API/tool call.
return {"id": lead.id, "name": lead.name, "stage": lead.stage}
```

```python
# server.py — upload_leads_csv()
# Removed: new_leads query + _schedule_cadence_for_lead loop
# Removed: try/except wrapper for CSV cadence scheduling
return {"created": created, "skipped": skipped, "errors": errors[:5]}
```

## Why This Exists

The scheduler timezone bug (naive vs aware datetime, IST/UTC mixup) caused UTC-stored cadence dates to fire immediately when the scheduler's IST adjustment compared them. Multiple cadence steps were stored with near-identical `scheduled_at` times, so 4+ messages fired in a burst.

The timezone fix normalized everything to UTC storage. But the core lesson is: **outbound communication must never be automatic.** It requires explicit user authorization every time.

## Enforcement

Any PR that adds `_schedule_cadence_for_lead()` calls to `create_lead`, `upload_leads_csv`, or any other automatic trigger point should be rejected. The only allowed call sites are explicit user-triggered endpoints.
