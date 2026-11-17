# [TOOL_CALL:] Strip Regex — Nested JSON Braces Fix (June 2026)

## The Bug

The `_strip_tool_markers` function used:
```python
r'\[TOOL_CALL:\s*\{.*?\}\s*\]'
```

With flat-format tool calls (`[TOOL_CALL: create_lead(name="John")]`), there were no nested braces — the non-greedy `{.*?}` correctly matched the single `{...}`.

With JSON-format tool calls (`[TOOL_CALL: {"tool": "web_search", "args": {"query": "Xpressbees"}}]`), the **nested** `{}` broke the regex:

- `\{` matches the outer `{`
- `.*?` (non-greedy) matches minimum to reach `}`
- `\}` matches the **inner** `}` (after `"Xpressbees"`)
- Remaining string is `}]` — `\s*\]` can't match because `}` is blocking it
- **Entire match fails** → no stripping → `[TOOL_CALL: {...}]` leaks to user

## The Fix

```python
r'\[TOOL_CALL:[^\]]*\]'
```

Match from `[TOOL_CALL:` to the nearest `]`. Since JSON tool calls don't contain literal `]` in their args, this correctly matches the entire block regardless of nested braces.

## Verification

Test with:
```python
import re
text = '[TOOL_CALL: {"tool": "web_search", "args": {"query": "Xpressbees"}}]'
result = re.sub(r'\[TOOL_CALL:[^\]]*\]', '', text)
assert result == ''
```

## All regexes in ARA that needed this fix (2 locations, same regex)

1. `_strip_markers()` function (server.py ~line 3004) — unused but kept for reference
2. Inline in `agent_chat()` response_clean (server.py ~line 5073) — the one that matters

Both were fixed in commit `1595220`.
