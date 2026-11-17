# Structural Tools-Text Cross-Check (June 16, 2026 — End of Session)

## Problem

The LLM would describe two actions in its response text ("Create deal + attach Ajay") but only generate ONE tool call (`create_deal`). The second action existed only in prose, never executed. This was the root cause of multiple "I asked for X and Y but only X happened" failures.

## Why Prompt Rules Weren't Enough

A self-audit rule ("4. TOOLS MATCH TEXT — Every action you describe MUST have a matching tool call") was added to the system prompt. But prompt rules are soft constraints — the LLM can still forget in the same generation where it writes about two actions.

## Structural Fix

A code-level cross-check runs **after every LLM response** in the observe loop, BEFORE the confirmation is shown to Greg:

```python
# server.py, observe loop (~line 5745)
_tool_names = [tc["name"] for tc in tool_calls]
_text_lower = (text or "").lower()

_action_map = {
    "attach_to_deal": ["attach", "link", "connect", "set.*contact"],
    "create_deal": ["create deal", "new deal", "add deal"],
    "create_lead": ["create lead", "new lead", "add lead"],
    "send_whatsapp": ["send whatsapp", "message", "text"],
    "send_email": ["send email", "email"],
    "update_lead": ["update lead", "change lead", "edit lead"],
    "update_deal": ["update deal", "change deal", "edit deal"],
    ...
}

_missing = []
for tool, patterns in _action_map.items():
    if tool not in _tool_names:
        for p in patterns:
            if re.search(p, _text_lower):
                _missing.append((tool, p))
                break

if _missing:
    _fix_prompt = f"Your response mentions actions without tool calls: {', '.join(_missing_descs)}. 
    Either add the missing tool calls or remove those actions from your text."
    loop_messages.append({"role": "user", "content": _fix_prompt})
    continue  # re-enter observe loop — LLM must fix before showing to user
```

## Detection Table

| Keyword in Text | Expected Tool | If Missing |
|----------------|--------------|------------|
| "attach", "link", "connect", "set contact" | `attach_to_deal` | LLM re-prompted |
| "create deal", "new deal", "add deal" | `create_deal` | LLM re-prompted |
| "create lead", "new lead", "add lead" | `create_lead` | LLM re-prompted |
| "send whatsapp", "message", "text" | `send_whatsapp` | LLM re-prompted |
| "send email", "email" | `send_email` | LLM re-prompted |
| "update lead", "change lead", "edit lead" | `update_lead` | LLM re-prompted |
| "update deal", "change deal", "edit deal" | `update_deal` | LLM re-prompted |
| "move deal", "change stage" | `update_deal_stage` | LLM re-prompted |
| "remind", "set reminder" | `set_reminder` | LLM re-prompted |

## Initial Bug: `not first_pass` Gate

The cross-check originally had `if _missing and not first_pass:` — it would only fire on the SECOND+ iteration of the observe loop. But the initial LLM generation is when the mismatch occurs. Fixed to `if _missing:` (always check).

## Relationship to Multi-Step Todo

The cross-check works with multi-step execution: when the LLM describes two actions, the cross-check ensures BOTH have tool calls. The todo system then executes them one at a time. Together: **cross-check prevents tool gaps, todo prevents batching confusion.**

## Verification

Before fix: "Create PayTM deal + attach Vinay Bhoj" → pending had only `create_deal`
After fix: Same request → pending has `['create_deal', 'attach_to_deal']` — both actions backed by tool calls
