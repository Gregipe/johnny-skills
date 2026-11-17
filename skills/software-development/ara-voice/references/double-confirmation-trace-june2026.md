# Double-Confirmation Bug Trace (June 2026)

## Symptom

Greg says "Send WhatsApp to Rajesh Sharma + update notes" via voice note.
Ava responds with "The WhatsApp failed due to a system error, but notes updated."
But the WhatsApp actually delivered to Rajesh. Greg: "Why did Ava's tool call fail?"

## Full Trace

### Turn 1 — Voice Note Processing

```
Voice note → Whisper → field-agent wrapper → agent_chat(POST, thread_id=coaching_thread)
```

Inside `agent_chat()`:
1. LLM generates response with BOTH `[CONFIRM_REQUIRED: Send WhatsApp to Rajesh...]` AND `[TOOL_CALL: {"tool": "send_whatsapp", ...}]`
2. Tool calls parsed from response
3. `needs_confirmation = True` (send_whatsapp is data_modifying)
4. Intent detector runs with:
   - "Ava proposed: [CONFIRM_REQUIRED: Send WhatsApp...]"
   - "User replied: [the field-agent wrapper text]"
5. **Intent detector returns REJECT** — the "user" message is a system wrapper, not Greg
6. `response = response_clean` (Ava's text without tool calls)
7. Voice handler sees `[CONFIRM_REQUIRED: ...]` → saves pending confirmation
8. **WhatApp tool never executed**

### Turn 2 — Greg Confirms

```
Greg: "send it"
→ _handle_owner_coach_whatsapp confirms via keyword regex
→ Sends exec_msg to agent_chat(POST, thread_id=None — fresh thread)
```

The exec_msg (call this Turn 2):
```
[CONFIRMED VOICE ACTION — EXECUTING]
Execute the action below immediately:
Send a WhatsApp/email to Rajesh Sharma...
...
RULES:
- Do NOT send any WhatsApp messages to any lead.  ← OLD CODE — now removed
```

Inside `agent_chat()` (Turn 2):
1. Fresh thread → no history
2. LLM generates response with tool calls
3. `needs_confirmation = True`
4. Intent detector runs with:
   - "Ava proposed: [cleaned response]"
   - "User replied: [CONFIRMED VOICE ACTION — EXECUTING]\nExecute..."
5. **The exec_msg format is machine-generated, not natural language**
   - Intent detector may return CONFIRM (word "CONFIRMED" present) or REJECT (format looks like instructions to AI, not a human reply)
   - Inconsistent behavior depending on LLM mood
6. If REJECT: tools don't execute → Ava's text response returned
7. Voice handler sends text to Greg as "Ava (confirmed): ..."
8. If CONFIRM: tools execute → WhatsApp may succeed or fail

### Why Greg saw "system error"

With the OLD code that had:

```python
f"- Do NOT send any WhatsApp messages to any lead.\n"
```

Ava saw this rule and didn't generate a WhatsApp tool call. She only generated `update_lead` for notes. The response went through the "I can't send WhatsApp" path.

With the STALE hardcoded context:

```python
f"Lead context — Thomas George (Swiggy), Bangalore\n"
```

Ava used "Thomas George (Swiggy)" as the lead for her notes update, even though the plan said "Rajesh Sharma."

### Why Greg thought the message went through

The WhatsApp message actually did reach Rajesh's phone — but NOT through Ava's tool execution. It was likely:
- Sent during a **previous successful** tool execution in another turn
- Or Greg checked WhatsApp on his phone and saw an earlier message

Ava's tool call NEVER executed during this flow due to the double-confirmation gate.

## Root Causes (Ranked by Priority)

| # | Cause | Fix |
|---|-------|-----|
| 1 | **Double-confirmation** — voice handler confirms with Greg, then `agent_chat` runs its own confirmation check against a machine-generated message | Skip confirmation in `agent_chat` when message starts with `[CONFIRMED VOICE ACTION — EXECUTING]` |
| 2 | **Stale hardcoded values** — `Lead context — Thomas George (Swiggy), Bangalore` was a test value left in production | Remove all hardcoded context from execution prompt; use plan + transcript only |
| 3 | **Over-aggressive guardrail** — "Do NOT send any WhatsApp messages" blocked legit confirms | Replace with "Execute exactly what was confirmed. Do not add extra actions." |
| 4 | **"Failed" not treated as "Error"** — `send_whatsapp` returns `"Failed to send..."` which doesn't start with `"Error"`, so the error path in `agent_chat` doesn't catch it | (Minor — the tool DID work, just inconsistent prefix) |

## The Fixes Applied

1. **Double-confirmation bypass** (`server.py ~line 5377`):
   ```python
   if user_msg.strip().startswith('[CONFIRMED VOICE ACTION — EXECUTING]'):
       is_confirmed = True
   ```
2. **Removed hardcoded context** (`server.py ~line 8676`):
   Deleted `f"Lead context — Thomas George (Swiggy), Bangalore\n"`.
3. **Replaced guardrail** (`server.py ~line 8680`):
   Changed `- Do NOT send any WhatsApp messages to any lead.` to `- Execute exactly what was confirmed. Do not add extra actions not mentioned in the plan.`
