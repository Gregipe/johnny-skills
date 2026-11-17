# Lead Stage Tracing — Methodology

How to trace a lead's stage through the system when the pipeline context disagrees with `get_lead_detail`.

## Pattern: Pipeline Context ≠ Tool Query

**Symptom:** Ava says "Lead X is at stage Y in the pipeline" (from injected context) but `get_lead_detail` returns a different stage Z.

**Root cause template:** The pipeline context is built ONCE at the start of `agent_chat` (line ~4899). `get_lead_detail` is a fresh DB read. Any commit between these two reads (from another thread, scheduler, or webhook) produces a discrepancy.

## Tracing Checklist

### 1. Check the Scheduler

The background scheduler (`_run_scheduler` at ~7499) polls every 30s for due actions. When a `ScheduledAction` fires via `_execute_action`, it can advance the lead's stage. Check:

- **WhatsApp path (~7093):** `if lead.stage == "new": lead.stage = "reached_out"` → present
- **Email path (~7110+):** No stage advancement → **GAP**. Email sends don't advance the pipeline
- **Call path (~7160+):** Only creates a notification, no stage change

If the first step in a cadence is email, the lead stays at `new` despite being contacted. Only a WhatsApp step later advances it.

### 2. Check Inbound Message Handling

`_handle_inbound_whatsapp` auto-advances:
- `new/reached_out` → `engaged`
- `dormant` → smart re-engagement (checks deal stage)

This happens outside the agent chat session, so the pipeline context may be stale from a turn that started before the inbound arrived.

### 3. Check the `get_lead_detail` Display

`get_lead_detail` (line ~3809) runs a fresh `resolve_lead()` + seperate `ScheduledAction` query. The `scheduled_at` shown is the **raw DB value** — cron actions reschedule to the NEXT occurrence after each fire, so the time shown may be the next run, not the original scheduled time.

### 4. Check Cron Rescheduling

When a cron action fires and succeeds, `_run_scheduler` resets `action.status = "pending"` with a new `scheduled_at`. The action stays in "pending" indefinitely (rescheduled, never "completed"). This is by design — the one action row perpetually cycles.

### 5. Check the Pipeline Context Build

The `lead_details` at line ~4912 queries ALL non-archived leads for the tenant. If a lead was just advanced by the scheduler but the agent_chat session started before the commit, the context is stale. This is a race condition, not a data bug.

## Example Trace

User asks: "Why does pipeline say 'new' but get_lead_detail says 'reached_out'?"

1. Check the lead's notes for recent stage change events
2. Check ScheduledAction for the lead — are there pending actions with past scheduled times?
3. Check _execute_action for the channel type of those pending actions
4. If channel is "email" and stage is still "new" → email branch missing stage advancement
5. If channel is "whatsapp" but didn't fire yet → the advancement happens at fire time, not at schedule time
6. If a WhatsApp action in the cadence fired BETWEEN 12:00 and 12:01 → normal race condition, confirm with scheduler logs
