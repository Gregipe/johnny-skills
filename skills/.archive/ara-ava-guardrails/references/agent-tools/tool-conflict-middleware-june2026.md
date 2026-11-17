# Tool Conflict Validation Middleware — June 2026

## Problem

Greg sent: "Hey Ava - can you move Rajesh Sharma to New stage."
Ava responded with BOTH `[TOOL_CALL: update_lead_stage]` AND `[TOOL_CALL: send_whatsapp]`.
The coaching thread had ~1200 messages, almost all about proposing WhatsApp to Rajesh — the context
pollution biased the LLM to over-generate the outreach tool alongside the requested stage change.

The canned response then said "Done! Message sent to Rajesh Sharma 🙌" regardless of what happened.

## Three-Layer Defense

### Layer 1: Prompt (Prevent)

Added a `## Tool Selection (HARD RULE)` section in `AGENT_SYSTEM_PROMPT_BASE` with explicit negative examples:

```
❌ User: "Move Rajesh to New stage" → [update_lead_stage] + [send_whatsapp]
✅ User: "Move Rajesh to New stage" → [update_lead_stage] ONLY
```

Sharpened tool descriptions with boundary rules:
- `update_lead_stage` — "NEVER combine with send_whatsapp or any outreach tool"
- `send_whatsapp` — "DO NOT call this when user says 'update' or 'move' stage"

### Layer 2: Middleware (Catch)

Added `_validate_tool_calls()` in `agent_chat()` right before the execution block (server.py ~line 5275):

```python
_CONFLICT_MAP = {
    "update_lead_stage": {"send_whatsapp", "trigger_cadence", "send_email",
                          "schedule_message", "schedule_email"},
    "update_lead": {"send_whatsapp", "trigger_cadence", "send_email",
                    "schedule_message", "schedule_email"},
    "update_deal_stage": {"send_whatsapp", "trigger_cadence", "send_email"},
    "update_deal": {"send_whatsapp", "trigger_cadence", "send_email"},
}

def _validate_tool_calls(tc_list, u_msg):
    """Strip outbound tools when user only asked for a stage/field update."""
    if not tc_list:
        return tc_list
    names = {t[0] for t in tc_list}
    forbidden = set()
    for primary, conflicts in _CONFLICT_MAP.items():
        if primary in names and (names & conflicts):
            forbidden.update(conflicts)
    if not forbidden:
        return tc_list
    stripped = [t for t in tc_list if t[0] not in forbidden]
    _log.warning(
        f"Tool call conflict detected: user='{u_msg[:80]}', "
        f"stripped={names - {t[0] for t in stripped}}, kept={ {t[0] for t in stripped} }"
    )
    return stripped
```

The middleware:
- Strips conflicted outreach tools, keeps the legitimate update tool
- Logs warnings for debugging
- Zero additional LLM cost (~20 lines of code)

### Layer 3: Response (Report Accurately)

Replaced the hardcoded canned response:

```python
# BEFORE — always said "Message sent"
lead_name = pending_tools[0].get("args", {}).get("lead_name", "")
if lead_name:
    response = f"Done! Message sent to {lead_name}. 🙌"
else:
    response = "Done! All set. 🙌"

# AFTER — builds from actual execution results
_action_lines = []
_lead_name = None
for _i, _r in enumerate(results):
    _tool_name = pending_tools[_i].get("tool", "")
    _parts = _r.split(":", 1)
    _action_text = _parts[1].strip() if len(_parts) > 1 else _r
    if not _lead_name and "✅" in _action_text:
        _after = _action_text.split("✅", 1)[1].strip()
        _candidate = _after.split(":")[0].strip() if ":" in _after else _after.split(".")[0].strip()
        if _candidate and len(_candidate) < 50:
            _lead_name = _candidate
    _action_lines.append(_action_text)
if _lead_name:
    response = f"✅ {_lead_name}: {' | '.join(_action_lines)}"
else:
    response = "✅ " + " | ".join(_action_lines)
```

Now the response shows e.g. "✅ Rajesh Sharma: Stage: reached_out → new" instead of "Done! Message sent to Rajesh Sharma."

## Research: Three Approaches for Tool Disambiguation

### Approach 1: Better Prompt + Negative Examples
**Cost:** Zero additional LLM calls
**Effectiveness:** Medium — helps but the LLM can still be overwhelmed by context pollution
**Best for:** Initial prevention; done in this session

### Approach 2: Post-Generation Validation Middleware
**Cost:** Zero additional LLM calls, ~20 lines of code
**Effectiveness:** High — catches the exact bug regardless of LLM behavior
**Best for:** Production guard; done in this session

### Approach 3: Two-Stage Intent Classification
**Cost:** +1 LLM call per turn
**Effectiveness:** Highest — separates "what to do" from "how to do it"
**Best for:** High-accuracy requirements; not implemented yet

### Key References from Research

- **Martin Fowler — Function Calling using LLMs:** Recommends structured action classes with intent-based dispatching. The `ShoppingAgent` pattern separates `decide_next_action()` (intent) from `execute()` (action). [Source](https://www.martinfowler.com/articles/function-call-LLM.html)
- **LiteLLM Tool Permission Guardrail:** Production pattern for allow/deny rules on tool calls with pre/post-call validation. [Source](https://docs.litellm.ai/docs/proxy/guardrails/tool_permission)
- **Sparkco — Advanced Tool Calling:** Recommends "structured, template-based reasoning" to improve reliability by guiding LLMs through interpretable steps before tool selection. [Source](https://sparkco.ai/blog/advanced-tool-calling-in-llm-agents-a-deep-dive)
