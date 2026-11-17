# Ava Error Handling Protocol (May 2026)

## Origin

Greg explicitly requested this after Ava dumped a raw error message when cadence triggering failed for Gregory Ipe:

> "We've got to do better because Ava just threw up the error without explaining why... What I would want Ava to become is less informative about the error and more agentic, which is: 'Okay I have run into this error. This is how I can solve this particular error and this is what you need to do to solve this particular error. This is what ideally should happen and these are the two options that I can do instead.'"

## Three Changes Made

### 1. Resolution-Oriented Error Messages (execute_tool)

Before: `"Could not trigger cadence for {lead.name}: {reason}"`

After: Each failure reason maps to a specific message with a `Resolution:` hint:

| Reason | New Message |
|--------|------------|
| `no cadence_type` | `"...no cadence type assigned. Resolution: Assign a cadence type first (cold/inbound/nurture) via the update_lead tool, then retry."` |
| `no config for {type}` | `"...no published template for '{type}'. Resolution: Publish the {type} template first via the Cadence Builder, then retry."` |
| `no steps` | `"...the template has no steps defined. Resolution: Add steps to the template in Cadence Builder and publish again."` |
| `stage={stage}` | `"...lead is at stage '{stage}' which is past the cadence window. Resolution: Reset the lead's stage to 'reached_out' or 'new' first, then retry. Alternatively, I can send a manual message right now."` |
| `{N} pending actions exist` | `"...{reason}. Resolution: Cancel existing pending actions first and retry — I can do both in sequence."` |

### 2. Error Handling Protocol in Ava's System Prompt

Added as a new section in `AGENT_TOOL_SCHEMA` (following the Guidelines section):

```
## ⚡ Error Handling Protocol

When a tool returns an error, follow these steps IN ORDER:

Step 1 — Diagnose on their behalf: Read the error and Resolution hint. 
Understand WHY it failed. Don't just repeat the error to the user.

Step 2 — Propose a fix: Say what needs to happen to resolve it. Be specific 
— mention the tool or action you can take.

Step 3 — Offer 1-2 alternatives you can do RIGHT NOW: Manual WhatsApp 
message? Schedule email? Change a lead's stage?

Step 4 — Keep it short: One paragraph, max. No error codes, no backend 
explanations, no "the system encountered an issue."

Bad example: "Looks like the system hit an internal error when trying to 
trigger the automated cadence. That's on the backend."

Good example: "Gregory Ipe doesn't have a cold cadence assigned. I can 
update his cadence type to 'cold' and retry, or I can send him a WhatsApp 
message right now. What works best?"
```

### 3. Reinforced Follow-Up Instruction (agent_chat)

The internal `follow_up` message that drives Ava's re-call after tool execution was updated from:

```
"The user is still waiting for your response. Acknowledge what failed, 
and offer alternatives or next steps."
```

To:

```
"The user needs a clear, action-oriented response. FOLLOW THE ERROR HANDLING 
PROTOCOL: diagnose why it failed, propose a fix you can do, and offer 1-2 
alternatives you can do right now. Do NOT output any [TOOL_CALL:] blocks 
— the tools have already run. Be concise. One paragraph max."
```

## Key Design Principles

1. **Ava is the interface, not the relay.** Raw error text should never reach the user. Ava translates backend errors into agentic, action-oriented responses.

2. **Every error has a fix path.** If the backend can't map the error to a specific fix, the fallback is still better than raw text: `"Could not trigger cadence for {lead.name}: {reason}."` — no Resolution hint, but clearly stated.

3. **Two recovery modes:**
   - Fix it myself: "I can update his cadence type and retry" (one more tool call)
   - Offer alternatives: "Or I can send a manual WhatsApp right now" (different action)

4. **One paragraph max.** No explanation of what went wrong on the backend, no error codes, no "the system encountered an issue."

## Files Modified

All in `server.py`:
- `execute_tool()` — trigger_cadence handler (~line 3089): resolution-oriented error messages
- `AGENT_TOOL_SCHEMA` string (~line 3890): Error Handling Protocol section added
- `agent_chat()` follow-up (~line 4128): reinforced instruction to follow the protocol

## Verification

Test by asking Ava to trigger a cadence for a lead that doesn't have one set up. Her response should:
1. Name the specific issue (e.g., "doesn't have a cadence type assigned")
2. Propose a fix (e.g., "I can assign one and retry")
3. Offer an alternative (e.g., "or I can send a manual message")
4. Stay within one paragraph
