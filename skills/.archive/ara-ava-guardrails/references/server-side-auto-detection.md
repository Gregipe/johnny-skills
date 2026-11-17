# Server-Side Auto-Detection & Auto-Execution of Tool Calls

When the LLM refuses to include `[TOOL_CALL:]` alongside a draft proposal, the server has two fallback mechanisms:

## 1. Auto-Detection (Creates Pending Tool Call)

After parsing any existing `[TOOL_CALL:]` blocks from the LLM response, the server checks if the response looks like a draft-approval request AND no tool calls were found:

```python
# Only fires on follow-up turns (has previous assistant message)
# to prevent false detection on the user's initial request
if not tool_calls and previous_assistant and ("Shall I send" in response or "shall I send" in response):
```

Then extracts lead name and message text using regex patterns:

**Lead name patterns (tried in order):**
```python
patterns = [
    r'(?:to|for|found|sending to)\s+\*?\"?\*?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\**\s*(?:on|via|over)?\s*(?:WhatsApp|email)?',
    r'(?:from|at)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s*[\)\]]',
    r'\*\*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\*\*',
]
```

The first pattern handles: "to **Rajesh Sharma**", "found **Rajesh Sharma**", 'for Rajesh Sharma on WhatsApp'.
The second handles: "Rajesh Sharma (Acme Manufacturing)" — captures the name before parens.
The third is a fallback: **Rajesh Sharma** (bold markdown).

**Message text patterns (tried in order):**
```python
patterns = [
    r'>\s*[\u201c\u201d""]([^\u201c\u201d""]{10,})[\u201c\u201d""]\s*',  # > "..." or > """
    r'>\s*\*([^*]{10,})\*\s*',   # > *italic*
    r'""([^"]{10,})""',           # ""..."" (escaped)
    r'"([^"]{10,})"',             # "plain quotes"
]
```

The key constraint: `{10,}` prevents matching empty strings or very short phrases.

When both lead name and message are found, a `send_whatsapp` tool call is created and injected into `response_original` for DB persistence:

```python
tool_calls.append(("send_whatsapp", {
    "lead_name": lead_match,
    "message": msg_match
}))
injected = f'\n[TOOL_CALL: {{"tool": "send_whatsapp", ...}}]'
response_original += injected
```

## 2. Auto-Execution (On Confirmation)

When the user confirms ("send it", "yes"), the server now parses tool calls from the **previous assistant response** (`response_original`) instead of relying on the LLM to generate a new `[TOOL_CALL:]` in the current response:

```python
re_pending = re.findall(r'\[TOOL_CALL:\s*(\{.*?\})\s*\]', response_original, re.DOTALL)
pending_tools = []
for tc_json in re_pending:
    try:
        pending_tools.append(json.loads(tc_json.strip()))
    except (json.JSONDecodeError, TypeError):
        pass

if pending_tools:
    # Execute pending tools immediately - no LLM call needed
    for tc in pending_tools:
        tool_name = tc.get("tool")
        args = tc.get("args", {})
        result = execute_tool(tool_name, args, db, wa, tenant_id)
    if no errors:
        response = "Done! Message sent. 🙌"
```

This bypasses the LLM entirely for the execution step — no more "Let me check what went wrong" or new drafts.

### Why This Works

The LLM's problem was: "I see my previous response without a `[TOOL_CALL:]` → something must have gone wrong → check error logs." The fix eliminates the need for the LLM to understand this at all. Server-side auto-execution just picks up the pending tool call from the original response and runs it.

### Pitfalls

- **Only fire on follow-up turns** — The `previous_assistant` check (`any(m.get("role") == "assistant" for m in messages)`) prevents auto-detection on the user's first message, which would cause the intent detector to classify the user's initial instruction as a "confirmation" and pre-emptively execute the tool
- **Don't override the response on success** — When auto-execution succeeds, set `response = "Done! Message sent. 🙌"` directly and skip the follow-up LLM call. If auto-execution fails (errors), fall through to the LLM follow-up so Ava can explain the error naturally
- **Skip follow-up block when auto-execution handles it** — The follow-up `if 'pending_tools' not in dir() or errors:` guard prevents the fallback code from overriding the clean "Done!" response
- **DB save uses `response_original` on the not-confirmed path** — Line 5710 saves `response_original` (with tool call) to DB so the next turn's LLM sees the prepared tool call. The user sees clean text via `response = response_clean`
