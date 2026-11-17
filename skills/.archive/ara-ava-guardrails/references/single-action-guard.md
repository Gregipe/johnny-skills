# Single-Action Guard (`_guard_single_action`)

## What
Code-level guard in server.py that prevents Ava from bundling unsolicited extra tool calls when Greg's message contains only one action verb.

## Problem
The LLM, primed by pipeline injection (leads/deals context), proposes additional actions alongside the one Greg requested. Example: "send a WhatsApp to Jimmie" → LLM also proposes `create_deal` for a "new" stage deal (Shriram Finance).

## How It Works
Scans user message for action verbs via regex word-boundary matching:
```
send → [send_whatsapp, send_email, send_whatsapp_to_owner]
create → [create_lead, create_deal, create_action_item]
update/change/edit → [update_lead, update_deal, update_action]
set/schedule → [set_reminder, set_cron, schedule_message, schedule_email]
...
```

If exactly ONE verb family is found and the LLM proposed multiple data-modifying tools, auto-trims to only tools matching that verb. Multi-verb requests ("create a deal and send a WhatsApp") are untouched.

## Location
- Function: `_guard_single_action()` — inserted after `_build_pending_description` in server.py
- Call site: Between `_built_desc = _build_pending_description(data_tools)` and `_pending_row = _AIStore(...)` in the observe loop

## Logging
Prefix: `SINGLE-ACTION-GUARD: trimmed N→M tools (verb=X, kept=[...], dropped=[...])`

## Pitfalls
- Does NOT fire on multi-action requests (two+ distinct verbs detected)
- Does NOT fire when the user's verb has no matching tool (fallback: keep all)
- Does NOT fire when all proposed tools already match the single verb family
