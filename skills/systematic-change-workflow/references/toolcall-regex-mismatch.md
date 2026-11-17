# [TOOL_CALL:] Regex Format Mismatch — Debugging Recipe

## The Bug

`[TOOL_CALL: {"tool": "web_search", "args": {"query": "Xpressbees"}}]` leaks into the user-facing response instead of being stripped.

## Root Cause Analysis

The strip regex `r'\[TOOL_CALL:\s*\{.*?\}\s*\]'` uses non-greedy `{.*?}`:

```
Input: [TOOL_CALL: {"tool": "x", "args": {"query": "y"}}]
                            ^                               ^
                            { starts                         } is inner brace
                                                             (closes "query": "y")
Match: {.*?} matches:   {"tool": "x", "args": {"query": "y"}
                                                              ^ stops at inner }
Remaining: }]
           ^ outer brace
^ \s*\] requires ] next — fails because } is in the way
→ Entire regex FAILS, nothing is stripped
```

## Fix

Replace `r'\[TOOL_CALL:\s*\{.*?\}\s*\]'` with `r'\[TOOL_CALL:[^\]]*\]'`.

This matches `[TOOL_CALL:` followed by any characters EXCEPT `]` until the first `]` — which is the tool call's closing bracket. JSON tool calls never contain literal `]` in their arguments, so this is safe.

## Verification

```python
import re
tests = [
    # JSON format with nested braces (the failing case)
    '[TOOL_CALL: {"tool": "web_search", "args": {"query": "news"}}]',
    # Old flat format
    '[TOOL_CALL: search_leads query="Raj"]',
    # Multiple tool calls
    '[TOOL_CALL: {"tool": "a"}}] [TOOL_CALL: {"tool": "b"}}]',
]
pattern = r'\[TOOL_CALL:[^\]]*\]'
for t in tests:
    result = re.sub(pattern, '', t)
    print(f"Input:  {t}")
    print(f"Output: '{result}'")
    assert result.strip() == ''
```

## Search Pattern to Find Affected Code

```bash
grep -rn 'TOOL_CALL.*\\\\[' *.py
# Or for running code:
grep -rn '\[TOOL_CALL' *.py | grep -v '\.pyc' | grep -v '#'
```

## Why This Happens

The LLM's tool call format changed from flat (`[TOOL_CALL: tool_name(arg=val)]`) to JSON (`[TOOL_CALL: {"tool": "name", "args": {...}}]`). The old regex was written for the flat format and never tested with nested JSON. Any regex that uses `{.*?}` (non-greedy brace matching) will break on nested `{}` — the non-greedy matcher stops at the FIRST `}`, which is the inner one.

## Prevention

When changing serialization format (flat → JSON, text → structured):
1. `grep -rn 'FORMAT_MARKER' *.py` to find ALL parsers, regex patterns, and strip functions
2. Test each with both the old AND new format
3. For JSON tool calls specifically, test with nested objects (args containing dicts)
4. Use `[^\]]*\]` (match to next `]`) instead of `\{.*?\}\s*\]` (match balanced braces) when the content between markers can contain nested braces
