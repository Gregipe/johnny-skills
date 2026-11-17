# Auto-Respond Hallucination Fix — June 2026

## Problem

`_ava_auto_respond()` called the LLM, then stripped all `[TOOL_CALL:]` blocks and sent the prose to the lead. If the LLM said *"I've updated your email to x@y.com"* with a tool call attached, the tool call was silently dropped — the lead got the claim but **no data was actually changed**.

The phantom-update detector (post-processing check) that existed in `agent_chat` did NOT apply to the auto-respond path. And the auto-respond prompt explicitly told the model "No special function calls needed" for qualification changes — encouraging prose-only claims.

## Root Cause

The stripping logic treated `[TOOL_CALL:]` markers as "leaked syntax" to be cleaned up, not as instructions to be executed. The auto-respond function had no concept of parsing and executing tool calls.

## Fix (3 parts)

### Part 1 — Execute tool calls before stripping

**File:** `server.py`, `_ava_auto_respond()` (~line 7800)

After getting the LLM response, before stripping markers:

```python
_auto_tool_calls = _parse_tool_calls(response)
_auto_executed = []
_auto_errors = []
for _tc_tool, _tc_args in _auto_tool_calls:
    _tc_result = execute_tool(_tc_tool, _tc_args, db, wa, tenant_id)
    _auto_executed.append((_tc_tool, _tc_result))
    if _tc_result.startswith("Error"):
        _auto_errors.append(f"Tool '{_tc_tool}': {_tc_result}")
```

`execute_tool()` is the same function used in the agent_chat path — it dispatches to `update_lead`, `create_lead`, `update_deal_stage`, etc.

### Part 2 — Phantom-update detection with auto-fix

Same regex as the agent_chat post-processing check:

```python
_update_claim_re = re.compile(
    r"(?i)(?:i[''']v[em]|i have|has been|updated|corrected|changed|set\s+(?:the|her|his|their|your)?\s*(?:email|phone|name))"
    r".{0,30}(?:email|phone|name|stage|status|notes|company)",
)
```

When a phantom update is detected (claim found + no update tool executed) AND no other tools were executed either:

1. **Acknowledge** — Send `"I've noted your request to update that information. Let me get that sorted for you."` via WhatsApp. Log as outbound conversation.
2. **Re-prompt** — Call the LLM with a correction prompt showing the original faulty response and requesting proper `[TOOL_CALL:]` block(s) for `update_lead`, `update_lead_stage`, `update_deal`, `create_lead`, or `create_deal`.
3. **Execute** — Parse tool calls from the fixed response and execute via `execute_tool()`.
4. **Follow-up (3 branches):**
   - **Tools succeeded** → `"All set! [field] updated to [value]."`
   - **Tools parsed but errored** → `"Sorry, I ran into an issue: [error]. Let me get a team member to help."`
   - **No tools parsed** (re-prompt also produced text without tools) → `"Sorry, I wasn't able to process that update. I'll have a team member help out."`
5. **Log** both the acknowledgment and follow-up as outbound conversations.
6. **Return True** — Skip the original hallucinated response entirely. Never send it to the lead.

#### Phantom-Update Fallthrough Fix (June 11, 2026)

Originally, the re-prompt fallthrough (when `_fixed` was empty or produced no tool calls) let the code fall through to the normal stripping + sending path — which would send the ORIGINAL hallucinated text to the lead alongside the acknowledgment. This defeated the purpose of the phantom detection.

**Fix:** Added an `else` clause to the `if _fixed and len(_fixed) > 20:` block. Now the three branches are explicit:
- Tools produced and executed → "All set!"
- Tools produced but errored → "Sorry, ran into issue"
- No tools produced → "Sorry, wasn't able to process"

All three paths `return True` so the original response is never sent.

**Re-prompt code:**

```python
_fix_prompt = (
    "You are a response corrector. The AI assistant (Ava) responded to a lead's request to update data.\n"
    "Ava said: \"" + _claim_text + "\" but there is no [TOOL_CALL:] block in her response.\n"
    "Without a [TOOL_CALL:], NO data is actually changed.\n\n"
    "Original lead message: " + lead_message + "\n\n"
    "Ava's faulty response: " + response + "\n\n"
    "Your job: Output ONLY the correct [TOOL_CALL:] block(s) "
    "(for update_lead, update_lead_stage, update_deal, create_lead, etc.) "
    "that Ava should have included to actually change the data."
)
_fixed = call_llm([{"role": "system", "content": _fix_prompt}], model="deepseek-v4-pro", temperature=0.3)
```

### Part 3 — Prompt hardening

Both "Qualification changes" entries in `AVA_AUTO_SYSTEM_PROMPT` changed from:

> *"If a lead shows interest or disqualifies, note it naturally in the conversation. No special function calls needed."*

To:

> *"If a lead shows interest or disqualifies that requires updating lead data (stage, phone, email, etc.), you MUST include a [TOOL_CALL: update_lead] block. Saying you made a change without [TOOL_CALL:] does NOTHING — no data is actually changed."*

## Greg's UX Preference (Critical)

**Do NOT send" "I'll check with my team and get back to you."**

Greg explicitly rejected this as the phantom-update fallback. His reasoning: *"the lead asked for an action and got a deflection — confusing."*

His preferred flow (which he approved):
1. **Acknowledge** — *"I've noted your request. Let me get that sorted for you."*
2. **Execute** — The tool call that should have been in the original response
3. **Confirm** — *"All set! I've updated [field] to [value]."*

> Acknowledge first, then update once it's done via the tool call.

## Verification

### Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_auto_respond.py` | 15 | Original auto-respond tests (happy path, stripping, fallback, LLM failure) |
| `tests/test_auto_respond_ext.py` | 8 | New: tool-call execution (3), phantom-update ack/fix/fail (5) |
| **Total** | **23** | Full auto-respond coverage |

### Test Scenarios Covered

1. **`test_happy_path_sends_message`** — Normal response sent to lead ✅
2. **`test_tool_call_executed_via_execute_tool`** — [TOOL_CALL:] executed before stripping ✅
3. **`test_tool_executed_before_stripping`** — Tool runs, markers cleaned from response ✅
4. **`test_tool_error_handled_gracefully`** — Tool error doesn't crash, response still sent ✅
5. **`test_phantom_update_sends_acknowledgment_first`** — Ack sent before re-prompt ✅
6. **`test_phantom_update_executes_tool_after_re_prompt`** — Re-prompted tool actually runs ✅
7. **`test_phantom_update_sends_follow_up`** — "All set!" message sent after execution ✅
8. **`test_phantom_update_without_re_prompt_fix_uses_safe_message`** — Re-prompt also fails → "sorry" ✅
9. **`test_phantom_update_not_triggered_when_tool_call_present`** — Tool + claim = normal path ✅

### Manual Verification

1. Send a lead message that should trigger an update (e.g., "my phone is now 9876543210")
2. Check the lead's WhatsApp — they should receive:
   - Acknowledgment message (if phantom detected)
   - Then a follow-up: "All set! I've updated the phone number..."
3. Check the DB — the lead's phone field should actually be updated
4. Check `conversations` table — should have 3 outbound entries (ack, follow-up, and the original response that was NOT sent)

## When to Tune

- The `_update_claim_re` regex pattern may need expanding if new phantom claim patterns emerge
- The re-prompt `call_llm` model is hardcoded to `deepseek-v4-pro` — if the lead context requires a different model, update this
- The acknowledgment message is hardcoded English — if multi-language support is added, make it configurable

## Related Files

- `server.py`, `_ava_auto_respond()` — implementation (~line 7800)
- `server.py`, `AVA_AUTO_SYSTEM_PROMPT` — prompt entries (~line 6323/6350)
- `tests/test_auto_respond.py` — 15 original tests
- `tests/test_auto_respond_ext.py` — 8 new tests (tool-call execution + phantom-update)
