# Format-String Crash in AGENT_SYSTEM_PROMPT_BASE

## The Bug (June 2026 Production Outage)

Added `[TOOL_CALL: {"tool": "web_search", "args": {"query": "..."}}]` to the `web_search` mandate in `AGENT_SYSTEM_PROMPT_BASE`. The unescaped curly braces `{` and `}` caused Python's `.format()` to interpret them as placeholder variables. Since no variable named `"tool"` (with quotes) exists, it raised `KeyError: '"tool"'` on every `agent_chat` call.

This crashed the server silently — no HTTP 500, just a broken response. The sidecar re-forwarded the same message, creating a loop of "message → crash → retry → crash" that generated 4+ identical Ava responses.

## Root Cause

```python
# server.py — AGENT_SYSTEM_PROMPT_BASE = """..."""
# This uses .format() at runtime:
system_prompt = AGENT_SYSTEM_PROMPT_BASE.format(
    agent_name=ctx["agent_name"],
    owner_name=ctx["owner_name"],
    ...
)
```

Any `{` in the template string that isn't one of the named placeholders (`{agent_name}`, `{owner_name}`, etc.) will be interpreted as a format variable reference. JSON code like `{"tool": "web_search"}` contains `{` followed by `"tool"` — Python sees this as `{`"tool"`}` and tries to find a variable called `"tool"` (literal double-quotes included), which doesn't exist.

## Diagnosis

```bash
# Check server logs
journalctl -u ara-server --no-pager -n 20 | grep -i "KeyError\|format"

# Look for KeyError at system_prompt.format() call
# line ~5160 in server.py: system_prompt = AGENT_SYSTEM_PROMPT_BASE.format(...)
```

## Fix

Escape ALL curly braces in JSON-like content within the template string:

```python
# WRONG — will crash
"You MUST call **web_search**... Output [TOOL_CALL: {\"tool\": \"web_search\", \"args\": {\"query\": \"...\"}}]"

# RIGHT — works
"You MUST call **web_search**... Output [TOOL_CALL: {{\"tool\": \"web_search\", \"args\": {{\"query\": \"...\"}}}}]"
```

Double braces `{{` and `}}` produce single literal braces `{` and `}` after `.format()` processes the string.

## Prevention

Before adding any JSON-like text to `AGENT_SYSTEM_PROMPT_BASE` or any other `.format()`-formatted string:

1. Check if the string uses `.format()`, `f"..."`, or `%` formatting
2. If it uses `.format()`, EVERY `{` and `}` in non-format content must be doubled
3. `AGENT_TOOL_SCHEMA` is safe — it's appended via `+=`, not `.format()`
4. When in doubt, check the code: `grep -n 'AGENT_SYSTEM_PROMPT_BASE.format' server.py`

## Verification

```bash
# Quick test — run the format call to see if it raises KeyError
python3 -c "
with open('server.py') as f:
    content = f.read()
# Extract the format call and test it
import re
# Or just: try the format string with sample args
"
```

Alternatively, test via the API:
```bash
curl -s -X POST http://localhost:8766/api/whatsapp/inbound \
  -H 'Content-Type: application/json' \
  -d '{"phone": "test", "message": "hello", "name": "test"}'
# Check if you get a 200 with a valid response, not a crash
```
