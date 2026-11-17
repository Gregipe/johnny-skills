# Multi-Step Todo Execution (June 16, 2026 — End of Session)

## Problem

When Greg gave Ava multiple actions in one message ("Create a deal for PayTM and attach Vinay Bhoj as the primary contact"), the LLM would:
1. Describe both actions in text but only tool-call one
2. Execute all tools at once with no progress visibility
3. Fail silently on attachment, user never knew what happened

## Architecture

Confirmed pendings with multiple tool calls now execute **one tool at a time**, preserving the remaining queue across confirmations:

```python
# server.py, agent_chat confirmation path (~line 6243)
if len(_pending_calls) <= 1:
    # Single tool (or last in queue): execute and finalize — mark fired
    ...
else:
    # Multi-step: execute ONE tool, keep rest queued
    _total = len(_pending_calls)
    _first = _pending_calls[0]
    _rest = _pending_calls[1:]
    
    _r = execute_tool(_first["tool"], _first["args"], ...)
    
    # Build progress message
    _next_desc = _build_pending_description(_rest[:1])
    _resp_text = f"✅ Step 1/2: {result}\n\n⏭ Next (2/2): {_next_desc}"
    
    # Update pending — keep rest for next confirmation
    _live.pending_tool_calls = json.dumps(_rest)
    _live.execution_state = "awaiting_approval"  # stay alive
```

## User Experience

```
Greg: "Create PayTM deal and attach Vinay Bhoj as primary contact"
Ava:  "Got it — 2 things: (1) create PayTM deal, (2) attach Vinay as contact. Shall I start?"
Greg: "yes"
Ava:  "✅ Step 1/2: Created deal PayTM. ⏭ Next (2/2): 🔗 Attach Vinay Bhoj to PayTM — continue?"
Greg: "yes"
Ava:  "✅ Step 2/2: Attached Vinay Bhoj to PayTM. All done!"
```

## Key Design Decisions

1. **Queue stored in existing pending ActionItem** — `pending_tool_calls` JSON shrinks as steps execute. No new DB columns needed.
2. **Each step is its own AgentChatMessage** — progress is visible in thread history.
3. **Last step marks pending as fired** — `len(_pending_calls) <= 1` triggers finalization.
4. **Sibling cancellation still runs on first step** — prevents stale pendings from interfering.
5. **Prompt teaches the multi-step pattern** — example flow in system prompt shows what to expect.

## Prompt Section

Added to Execution Intent Protocol in system prompt:

```
When Greg asks for multiple actions in one message, break it into a numbered plan:
1. Count and describe each action: "Got it — 3 things: (1) create deal X, (2) attach Y, (3) set reminder."
2. Include ALL tool calls in your response. System executes one at a time.
3. After each step, Greg sees progress and continues.
4. If any step fails, system pauses and asks for clarification.
```

## Verification

Tested end-to-end: "Create PayTM deal + attach Vinay Bhoj" → 2 tools detected → step 1 confirmed → step 2 confirmed → deal with primary contact synced.
