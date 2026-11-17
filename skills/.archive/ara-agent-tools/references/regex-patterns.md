# Regex Patterns for Parsing LLM Tool Calls

## Parsing `[TOOL_CALL: {json}]` Blocks

```python
import re

# Match [TOOL_CALL: {json with nested braces}] — one or more
pattern = r'\[TOOL_CALL:\s*(\{.*?\})\s*\]'
matches = re.findall(pattern, response, re.DOTALL)
```

**Why this works with nested JSON:**
- `\{.*?\}` — non-greedy, tries to match as few chars as possible
- `\s*\]` — after the JSON, there must be optional whitespace then `]`
- Regex engine backtracks: the lazy `.*?` extends until the `]` finds a match
- Since the outermost `{`-to-`}` is the full JSON and the `]` comes after it, backtracking lands correctly on the full JSON string
- `re.DOTALL` makes `.` match newlines (important if LLM output has line breaks)

**Multiple tool calls in one response:**
Non-greedy behavior + separate `[TOOL_CALL: ...]` delimiters means each call is matched independently:
```
[TOOL_CALL: {"tool": "a", ...}]
Some text...
[TOOL_CALL: {"tool": "b", ...}]
```
→ Two separate matches, parsed independently.

## Cleaning Tool Calls from Response

```python
# Remove ALL [TOOL_CALL: {json}] blocks
clean = re.sub(r'\[TOOL_CALL:\s*\{.*?\}\s*\]', '', response, flags=re.DOTALL)

# Remove old-style command markers
clean = re.sub(r'\[(SEARCH|FETCH_URL|CADENCE_TRIGGER):\s*.*?\]', '', clean)
clean = re.sub(r'\[WHATSAPP:\s*.*?\s*\|\s*.*?\]', '', clean)
clean = clean.strip()
```

## Old-Style Pattern Translation

When an LLM still outputs old-format commands (backward compat), parse and translate:

```python
# SEARCH
search_match = re.search(r'\[SEARCH:\s*(.*?)\]', response)
if search_match:
    tool_calls.append(("web_search", {"query": search_match.group(1).strip()}))

# FETCH_URL
url_match = re.search(r'\[FETCH_URL:\s*(.*?)\]', response)
if url_match:
    tool_calls.append(("fetch_url", {"url": url_match.group(1).strip()}))

# WHATSAPP: number | message
wa_match = re.search(r'\[WHATSAPP:\s*(.*?)\s*\|\s*(.*?)\]', response)
if wa_match:
    tool_calls.append(("send_whatsapp", {
        "lead_name": wa_match.group(1).strip(),
        "message": wa_match.group(2).strip()
    }))

# CADENCE_TRIGGER
cadence_match = re.search(r'\[CADENCE_TRIGGER:\s*(.*?)\]', response)
if cadence_match:
    tool_calls.append(("trigger_cadence", {"lead_name": cadence_match.group(1).strip()}))
```

## Debugging Regex

```python
# Quick test in Python
import re, json
response = '[TOOL_CALL: {"tool": "update_lead", "args": {"lead_name": "Gregory Ipe", "fields": {"stage": "qualified"}}}]'
matches = re.findall(r'\[TOOL_CALL:\s*(\{.*?\})\s*\]', response, re.DOTALL)
print('Match count:', len(matches))
if matches:
    tc = json.loads(matches[0])
    print('Tool:', tc.get('tool'))
```
