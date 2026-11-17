# Response Duplication Fix (Text Appearing Twice) — June 2026

## Problem

Ava's response contained the same text block twice within the same WhatsApp message:
```
Good question! I tried looking up Acme Manufacturing...
[TOOL_CALL: ...]
Good question! I tried looking up Acme Manufacturing...
[TOOL_CALL: ...]
```

## Root Cause

When Ava's first response contained a tool call marker (`[TOOL_CALL: {"tool":"web_search", ...}]`), the code:
1. Extracted text as `response_clean` (stripping tool call markers)
2. Injected `response_clean` as an assistant message in the messages array
3. Made a second LLM call with the follow-up instruction

The second LLM call saw its own previous response in context and echoed parts of it back, creating duplication:
```python
messages.append({"role": "assistant", "content": response_clean})  # ← THIS caused the echo
messages.append({"role": "user", "content": follow_up})
```

## Fix Applied

**File:** `server.py`

Two changes in BOTH the confirmed and unconfirmed code paths:

1. **Removed `response_clean` injection** — the LLM doesn't need to see its own text:
```python
# REMOVED
messages.append({"role": "assistant", "content": response_clean})

# KEPT
messages.append({"role": "user", "content": follow_up})
```

2. **Added "DO NOT repeat" to the follow-up instruction:**
```python
# Before
"The user is still waiting for your response. Summarize what was done..."

# After
"Respond naturally to the user's original message. DO NOT repeat what you already said — the user saw it."
```

## Files Modified

- `server.py` — both confirmed (line ~5019) and unconfirmed (line ~5053) code paths in `agent_chat()`

## Verification

- Send a query that triggers a tool call (e.g., "search for X company")
- Check the response for duplicated text
- The response should flow naturally: tool result → single coherent answer, no echo
