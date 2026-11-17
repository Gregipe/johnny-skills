# Voice Note Confirmation Gate Skip (June 14, 2026)

## Incident

Greg sent two voice notes asking Ava to set reminders for Rajesh Sharma. Both times Ava correctly transcribed and proposed the action, asking "Want me to set it?" But when Greg replied "Yes" or "Yes set it in", Ava completely lost context — responding with "Arun Matthew?" (wrong entity) or "Great — what do you need?" (blank slate).

## Full timeline (UTC)

### Interaction 1 (14:44:05): Voice note → proposal
```
14:44:05 agent_turn → POST /api/agent/chat/3e736242 → 200 OK
14:44:05 Voice response sent: "Here's what I picked up... Set a reminder..."
         DB check: TOOL_CALL=False, ACTION=False, PENDING=False
```

### Interaction 2 (14:44:21): "Yes set it in" → confusion
```
14:44:21 msg_preview=Yes set it in → LLM call (1s)
14:44:32 agent_turn → "...Arun Matthew's missing phone/company details?..."
         DB check: TOOL_CALL=False, ACTION=False, PENDING=False
```

### Interaction 3 (15:00:58): Second voice note → same proposal
```
15:00:51 Transcribed (16s): "Hey Eva can you... set a reminder to message Rajesh Sharma..."
15:00:58 agent_turn → "Here's what I picked up... Reminder to send him pricing..."
         DB check: TOOL_CALL=False, ACTION=False, PENDING=False
```

### Interaction 4 (15:01:09): "Yes" → blank slate
```
15:01:05 msg_preview=Yes → LLM call (1s)
15:01:09 agent_turn → "Great — what do you need?"
         DB check: TOOL_CALL=False, ACTION=False, PENDING=False
```

### Interaction 5 (15:02:24): Manual text → ActionItem FINALLY created
```
15:02:19 msg_preview=Set a reminder : - Who: Rajesh Sharma...
15:02:24 agent_turn → "[PENDING - Reply 'send it' or 'confirm' to proceed]"
         DB check: TOOL_CALL=False, ACTION=False, PENDING=True
         pending_tool_calls: [{"tool": "set_reminder", "args": {...}}]
         description: ""  ← EMPTY
```

## Root cause chain

### Why no ActionItem was created for voice notes

1. Voice note arrives at `whatsapp_voice_inbound()` → posted to agent_chat with `voice_note=True`
2. LLM generates proposal asking "Shall I set a reminder?" **BUT drops `[TOOL_CALL:]`** (same old bias: asking permission + including tool call = contradiction)
3. Ask-gate at line 5075: `is_data_modifying = any(not get_tool_read_only(tc["name"]) for tc in tool_calls)` → `any([])` → `False`
4. `confirmed = not is_data_modifying` → `True`
5. `if not confirmed and is_data_modifying:` → `False and False` → **SKIPPED**
6. **No `ActionItem(execution_state="awaiting_approval")` is created**
7. When Greg replies "Yes set it in", `_live_pending_for_tenant()` returns None
8. Message falls through to normal observe loop → LLM sees "Yes set it in" with zero context → hallucinates

### Why the manual text DID create an ActionItem

The structured, bullet-point format made the LLM include `[TOOL_CALL: set_reminder]` → `is_data_modifying = True` → ActionItem created. But `description=""` because `resp_clean` was empty after stripping `[ACTION: ASK]`.

## What this breaks

The entire DB-backed confirmation pipeline (commit 0873bb3) is useless when voice note proposals omit `[TOOL_CALL:]`. The pipeline's entry condition (`is_data_modifying = True`) requires tool calls. No tool calls → no pending row → no confirmation → bare message with zero context.

## Fix direction

The existing server-side auto-detection for `send_whatsapp` patterns ("Shall I send?" + quoted text) catches the same LLM behavior but only for one tool type. The fix needs to generalize to ALL tool types:

- **(a)** Server-side parser that detects proposal text ("Shall I set a reminder?", "Want me to create a lead?") and auto-generates `[TOOL_CALL:]` blocks from context
- **(b)** Re-call mechanism: when voice note proposal has no tool calls AND contains proposal phrasing ("Shall I"/"Want me to"/"Should I"), force a second LLM call to add the tool call

The `_classify_confirmation("", user_msg)` call with empty description is a secondary issue — the classifier gets no proposal context when it needs it most.
