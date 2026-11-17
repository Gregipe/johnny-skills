# Tool Call Marker Stripping in WhatsApp — June 2026

## Problem

Raw `[TOOL_CALL: {"tool":"web_search",...}]` text appeared in WhatsApp messages to Greg. Even though the re-call LLM instruction says "Do NOT output [TOOL_CALL:] blocks," the LLM sometimes ignores this.

## Root Cause

The `agent_chat()` endpoint returns the raw LLM response, which may contain `[TOOL_CALL:...]` markers if the LLM disobeyed the instruction. The coaching handler (`_handle_owner_coach_whatsapp`) sends this verbatim to WhatsApp without stripping.

## Fix

Added regex-based stripping in the coaching handler BEFORE formatting the WhatsApp message:

```python
# In _handle_owner_coach_whatsapp(), after agent_chat response:
import re as _re
ava_reply = _re.sub(r'\[TOOL_CALL:\s*\{.*?\}\s*\]', '', ava_reply, flags=_re.DOTALL)
ava_reply = _re.sub(r'\[(SEARCH|FETCH_URL|CADENCE_TRIGGER|WHATSAPP):.*?\]', '', ava_reply)
ava_reply = ava_reply.strip()
```

This strips these patterns:
- `[TOOL_CALL: {"tool": "...", "args": {...}}]`
- `[SEARCH: query]`
- `[FETCH_URL: url]`
- `[CADENCE_TRIGGER: name]`
- `[WHATSAPP: name | message]`

## Why Not Fix the LLM Instead?

The LLM-level fix is still in place (follow-up says "DO NOT output [TOOL_CALL:] blocks"), but LLMs are unreliable about following formatting constraints embedded in content-heavy instructions. The regex strip is a safety net that guarantees no marker ever reaches the user.

## Files Modified

- `server.py` — `_handle_owner_coach_whatsapp()`, after `resp.json()` and before `wa.send_to_jid()`

## Pitfalls

1. **Don't strip before saving to DB** — the raw response in the DB preserves the original LLM output for debugging. Only strip at the display layer.
2. **DOTALL flag is required** — JSON can span multiple lines. Without `re.DOTALL`, the `.*?` won't match newlines.
3. **Non-greedy matching** — `.*?` with `\]` anchor ensures the regex matches the innermost complete tool call, not everything between `[TOOL_CALL:` and the last `]` in the response.
