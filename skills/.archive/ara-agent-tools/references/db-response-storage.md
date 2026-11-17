# DB Response Storage: Rendered Results vs Raw LLM Response

## The Bug

After tool execution, `db_response` was set to `_stripped` — which is `response_original` with
only `[ACTION: NOW/ASK]` stripped. The `[TOOL_CALL: {...}]` blocks were still present.

Meanwhile, `response` was set to `render_results(_results, channel=_channel)` — the formatted
user-facing results.

When conversation history was loaded from the DB, the raw `[TOOL_CALL: ...]` text appeared
because the tool call blocks were never stripped from the stored message.

## The Fix

```python
# BEFORE (broken):
response = render_results(_results, channel=_channel)
db_response = _stripped  # ❌ raw LLM response still has [TOOL_CALL:]

# AFTER (fixed):
response = render_results(_results, channel=_channel)
db_response = response   # ✅ rendered results — no raw tool call text
```

Also applies to the read-only tool path and the no-tool-call path.

## What Gets Stored vs What Gets Displayed

| Variable | What it contains | Where used |
|----------|-----------------|------------|
| `response` | Rendered tool results (or cleaned LLM text) | Sent to user via HTTP response |
| `response_clean` | LLM response with `[TOOL_CALL:]` stripped | Shown as proposal text when tools aren't executed |
| `response_original` | Raw LLM response (untouched) | Used to build `_stripped` (deprecated) |
| `db_response` | What gets stored in DB `AgentChatMessage.content` | Should always be `response` (rendered) |

## Related

- `[TOOL_CALL:]` strip regex fix in `ara-agent-tools` Pitfall #2
- `ara-message-pipeline-reliability` for DB commit retry patterns
