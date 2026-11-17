# ARA Voice Phase 2 — Write Tools with Voice-Propose + Chat-Confirm

Date: 2026-07-04

Phase 2 lets voice Ava PROPOSE write operations by voice. The actual execution stays
in the dashboard chat confirmation gate (typing "yes"/"no").

## Architecture

Two separate tool lists in `/opt/ara/server.py`:

- `VOICE_SAFE_TOOLS` — 18 read-only tools, auto-execute via `/api/voice/tool`
- `VOICE_WRITE_TOOLS` — 32 write tools, staging via `/api/voice/stage`

`/api/voice/tools` returns BOTH lists with `read_only` flag per tool.
`/api/voice/tool` still REJECTS writes (double safeguard).

## Confirmation Flow

```
User (voice): "Create a lead for Rajesh at Acme"
Ava (voice): "➕ Add lead: Rajesh — shall I create it? Check your dashboard."
  → ActionItem created (execution_state=awaiting_approval, action_type=voice_pending_confirmation)
  → ARA's existing chat confirmation flow sees this ActionItem
  → Dashboard chat shows the proposal
User types: "yes"
  → ARA's _classify_confirmation() matches → execute_tool() → lead created
  → ActionItem: execution_state=fired, outcome_state=resolved
```

## New Endpoints

### POST /api/voice/stage
Body: `{secret, tool_calls: [{tool, args}], tenant_id}`
- `tool_calls` is an ARRAY (supports multiple tool calls per staging action)
- Only one voice pending action per tenant at a time (auto-cancels previous)
- Creates ActionItem with `action_type="voice_pending_confirmation"`, `execution_state="awaiting_approval"`
- Returns `{ok: true, pending_id, description}`

### POST /api/voice/confirm
Body: `{secret, pending_id, tenant_id, cancel: bool}`
- BOTH `pending_id` AND `tenant_id` are required
- `cancel=true` → sets execution_state=cancelled, doesn't execute
- `cancel=false` → parses pending_tool_calls JSON, calls execute_tool() for each
- Returns `{ok: true, summary}` or `{ok: false, message: "No pending voice action found"}`

### GET /api/voice/pending
Query: `?secret=...&tenant_id=...`
Returns the current pending voice action for a tenant (if any).

## Voice Agent Changes

### voice_tools.py — Routing by read_only flag

```python
if read_only:
    # POST /api/voice/tool → immediate execution
    resp = await http_client.post(f"{ARA_BASE}/api/voice/tool",
        json={"secret": secret, "tenant_id": tenant_id, "tool": tool_name, "args": args})
else:
    # POST /api/voice/stage → staged for confirmation
    tool_calls = [{"tool": tool_name, "args": args}]
    resp = await http_client.post(f"{ARA_BASE}/api/voice/stage",
        json={"secret": secret, "tenant_id": tenant_id, "tool_calls": tool_calls})
```

Key: write tools use `tool_calls` (array), read tools use `tool` (single name).

### bot.py — System Prompt

```
You can make changes to the CRM by voice. When the user asks you to create,
update, send, schedule, or modify anything, use the appropriate write tool
to PROPOSE the change. The tool will stage it for confirmation. Tell the
user what you're proposing and say "check your dashboard to confirm."
Never execute a write action without confirmation — always ask.
```

## VOICE_WRITE_TOOLS (32 tools)

`update_lead_stage`, `update_lead`, `create_lead`, `create_action`, `set_reminder`,
`update_deal_stage`, `update_deal`, `create_deal`, `create_action_item`,
`attach_to_deal`, `detach_from_deal`, `send_whatsapp`, `send_whatsapp_instantly`,
`send_whatsapp_to_owner`, `send_email`, `send_attachment`, `send_internal_note`,
`schedule_follow_up`, `schedule_message`, `schedule_email`, `trigger_cadence`,
`cancel_scheduled`, `mark_meeting_booked`, `evaluate_qualification`, `log_insight`,
`save_learning`, `save_memory`, `add_to_watchlist`, `resolve_watchlist_item`,
`import_leads_from_text`, `upload_document`, `update_action`

Excluded system-level tools: `add_skill`, `set_cron`, `debug_schedule`,
`diagnose_failure`, `check_health`, `escalate_to_human`, `log_capability_request`,
`read_code`, `read_logs`, `read_system_logs`, `query_database`.

## Design Decisions

- `action_type = "voice_pending_confirmation"` — distinguishes voice-staged actions
  from chat pending confirmations (`action_type = "pending_confirmation"`).
  `_live_pending_for_tenant` is updated to EXCLUDE `voice_pending_confirmation`
  so the chat confirm flow doesn't catch voice-staged items.
- `_live_voice_pending_for_tenant()` — separate helper for voice-specific lookups.
- Only one voice pending per tenant: staging a new one auto-cancels the previous.
- `/api/voice/confirm` requires `tenant_id` alongside `pending_id` for tenant isolation.
- No dashboard changes — voice-staged ActionItems surface through the existing
  chat confirmation flow. The user sees the proposal and types "yes"/"no" in chat.
