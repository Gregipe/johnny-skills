# Model Routing Keyword Gap (June 2026)

## The Bug

User asks "Can you start an outbound sequence to Gregory Ipe?" — Ava responds "I tried to start the outbound cadence for Gregory Ipe, but the system hit an internal error on that one" and offers manual fallback. The server log shows:

```
Model routing: user_msg_keywords=False, model=deepseek-v4-flash
ENFORCER SKIPPED: intent=False has_data_tool=False is_q=True msg=hi ava! can you start an outbound sequence to greg
```

The LLM never attempted to call the `trigger_cadence` tool. No UnboundLocalError, no crash — just a conversational "sorry, internal error" response. The tool works fine (verified via direct API call).

## Root Cause

The `_model_routing_keywords` set in `agent_chat()` (server.py ~line 4870) decides whether the request uses **deepseek-v4-pro** (strong tool-calling) or **deepseek-v4-flash** (fast, weaker tool calling):

```python
_model_routing_keywords = {
    "email", "phone", "name", "stage", "notes", "company", "deal", "lead",
    "update", "change", "correct", "fix", "add", "create", "save", "set",
    "schedule", "remind", "evaluate", "qualify", "analyze", "research", "compare",
    "search", "move", "status", "stage"
}
```

The user's message: "Can you **start** an **outbound** **sequence** to Gregory Ipe?"
- "start" — NOT in the keyword set
- "outbound" — NOT in the keyword set
- "sequence" — NOT in the keyword set
- "cadence" — NOT in the keyword set

Result: routed to **deepseek-v4-flash**. Flash doesn't reliably call `trigger_cadence` (a complex tool with specific args), so it generated a fake "internal error" response instead.

## The Fix

Added the missing keywords to `_model_routing_keywords`:

```python
_model_routing_keywords = {
    "email", "phone", "name", "stage", "notes", "company", "deal", "lead",
    "update", "change", "correct", "fix", "add", "create", "save", "set",
    "start", "outbound", "sequence", "cadence", "send",
    "stop", "pause", "cancel",
    "schedule", "remind", "evaluate", "qualify", "analyze", "research", "compare",
    "search", "move", "status", "stage"
}
```

Truth worth noting is, "send" is already checked in the enforcer (`_data_keywords`) but was NOT in the model routing keywords — meaning a user saying "send a message" would route to Flash and never call `send_whatsapp`.

## How to Diagnose

When a user reports Ava saying "internal error" or offering manual fallback for a tool call:

1. **Check the server log for the model routing line:**
   ```bash
   journalctl -u ara-server --since "5 minutes ago" | grep "Model routing"
   ```
   If it says `user_msg_keywords=False, model=deepseek-v4-flash` for a message that clearly requests a tool action → keyword gap.

2. **Test the tool directly to confirm it works:**
   ```bash
   curl -s -X POST http://localhost:8766/api/cadence/trigger/lead/{lead_id}
   ```
   If the tool works directly but Ava couldn't call it → routing issue, not tool bug.

3. **Check which words the user used:**
   The keyword set uses `set(user_msg.lower().split())` — intersection with the keyword set. If critical verbs like "start", "stop", "send", "pause" are missing, add them.

## Key Difference: Enforcer Keywords vs Model Routing Keywords

ARA has TWO separate keyword sets, and they serve different purposes:

| Set | Location | Purpose | Consequence of miss |
|-----|----------|---------|---------------------|
| `_model_routing_keywords` | Line ~4870 | Decides Flash (cheap) vs Pro (capable) | Flash gets tool-calling requests it can't handle → "internal error" |
| `_data_keywords` | Line ~4905 | Enforcer fires when intent found but no tool call in response | Tool call is silently skipped (enforcer doesn't re-fire) |

They are NOT the same set and should be kept in sync. Every keyword in `_data_keywords` that could appear in a user's request should also be in `_model_routing_keywords`, or the request routes to Flash which may not generate a tool call at all.

## Related

- `ara-agent-chat-debugging` — The enforcer logic and intent detection (separate concern from model routing)
- `ara-cadence-logic` — The trigger_cadence tool itself
