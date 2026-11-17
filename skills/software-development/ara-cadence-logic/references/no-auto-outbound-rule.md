# HARD RULE: Zero Auto-Outbound from Ava

**Effective: June 15, 2026. Non-negotiable.**

## Rule

No outbound communication (WhatsApp, email, or any channel) from Ava under any circumstances unless:
1. Greg explicitly authorizes it, OR
2. A formal outbound cadence has been explicitly scheduled via API or tool call

## What Changed

Two call sites removed from `server.py`:

1. **`create_lead`** (line ~1177): Removed `_schedule_cadence_for_lead(lead, db)` — even leads assigned to Ava no longer get auto-cadenced
2. **`upload-csv`** (line ~1589): Removed cadence scheduling loop for newly created CSV leads

## Why

On June 15, 2026, four back-to-back WhatsApp messages ("Hi Prashant Rai, just checking in...") were sent to a live, unassigned lead because the cadence was auto-scheduled at lead creation time. The lead (`06544ce3`, Prashant Rai) had `assigned_agent=""` — Ava had no business messaging him. Two emails also went out simultaneously.

The messages fired at 19:40-19:42 IST from cadence ScheduledActions that were queued before the bug fix deployed.

## How Cadence Is Now Triggered

Only via explicit invocation:
- **API:** `POST /api/tenants/{tenant_id}/leads/{lead_id}/cadence`
- **Tool call:** `schedule_cadence` from the agent

Both paths call `_schedule_cadence_for_lead()` — the function still exists and works correctly when explicitly invoked.

## Verification

After any cadence or lead creation change, verify no auto-triggers exist:

```bash
grep -n "_schedule_cadence_for_lead" /opt/ara/server.py
```

Expected output (only explicit trigger paths):
```
409:    schedule_cadence_for_lead as _schedule_cadence_for_lead,
3800:   result = _schedule_cadence_for_lead(lead, db)
```

Must NOT appear in `create_lead` or `upload-csv` functions.

## Incident: Prashant Rai Cadence Spam

| Detail | Value |
|---|---|
| Lead | Prashant Rai (`06544ce3`) |
| Assigned agent | None (empty string) |
| Messages sent | 4 WhatsApp + 2 email (all identical) |
| Content | "Hi Prashant Rai, just checking in -- wanted to see if you had any thoughts since we last spoke..." |
| Time | 19:40-19:42 IST, June 15, 2026 |
| Root cause | `_schedule_cadence_for_lead()` called in `create_lead` before the fix |
| Status | All 12 cadence ScheduledActions cancelled. 1 pending email cancelled. |
