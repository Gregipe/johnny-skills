# Ava Tool-Calling Architecture

How to wire up CRM features so Ava (the LLM agent) can invoke them via structured tool calls.

## Architecture Overview

```
User message → agent_chat() → LLM (DeepSeek V4 Flash)
  ↓
  LLM outputs [TOOL_CALL: {"tool": "name", "args": {...}}] in its response text
  ↓
  Server parses ALL [TOOL_CALL: ...] blocks from the response
  ↓
  execute_tool() dispatcher routes to the appropriate Python function
  ↓
  Tool executes against the DB (same code paths as the REST API)
  ↓
  Results fed back to LLM in a Stage 2 re-call
  ↓
  LLM responds naturally to the user with what happened
```

## Key Files

- **`server.py`** — `execute_tool()` dispatcher (~200 lines), `resolve_lead()`/`resolve_deal()` helpers, and the `agent_chat()` parsing logic
- **`AGENT_SYSTEM_PROMPT_BASE`** + **`AGENT_TOOL_SCHEMA`** — split system prompt (BASE has format vars, TOOL_SCHEMA has JSON examples with curly braces that would break `.format()`)
- **System prompt tool definitions** — `AGENT_TOOL_SCHEMA` constant in `server.py` — lists all 11 tools with args schemas and examples

## Tool Format

Ava outputs tool calls inline in her response text:

```
[TOOL_CALL: {"tool": "update_lead", "args": {"lead_name": "Gregory Ipe", "fields": {"stage": "qualified", "notes": "Good fit"}}}]
```

Ava can output MULTIPLE tool calls in a single response. They execute in order. All results are fed back to the re-call.

## Backward Compatibility

Old patterns still work and get translated to tool calls internally:
- `[SEARCH: query]` → `web_search`
- `[FETCH_URL: url]` → `fetch_url`
- `[WHATSAPP: number | message]` → `send_whatsapp` (maps number to lead_name)
- `[CADENCE_TRIGGER: name]` → `trigger_cadence`

## Adding a New Tool

1. **Add the tool implementation** as an `elif` branch in `execute_tool()` in `server.py`:
   ```python
   elif tool_name == "my_new_tool":
       arg1 = args.get("arg1", "")
       if not arg1: return "Error: 'arg1' is required"
       # ... do the work ...
       return f"Result: {result}"
   ```

2. **Add it to the system prompt** (`AGENT_TOOL_SCHEMA`):
   ```
   X. my_new_tool — Description
      Args: {"arg1": "...", "arg2": "..."}
   ```

3. **Add an example** in the examples section of `AGENT_TOOL_SCHEMA`.

That's it. No new regex pattern, no new endpoint needed — the `[TOOL_CALL: ...]` format handles any tool generically.

## Regex Details

The parsing regex is:
```python
r'\[TOOL_CALL:\s*(\{.*?\})\s*\]'
# Matches [TOOL_CALL: {any JSON}] with re.DOTALL flag
```

This uses **non-greedy** `.*?` with **backtracking** from the closing `]`. The key insight: the `\s*\]` at the end forces backtracking so `.*?` extends past inner `}` characters until it reaches the closing `]` after the full JSON. Works for nested JSON at any depth because the regex engine backtracks until it finds a `]` after optional whitespace.

For **cleaning** tool calls from the response before the re-call:
```python
re.sub(r'\[TOOL_CALL:\s*\{.*?\}\s*\]', '', response, flags=re.DOTALL)
```

## Stage 2 Re-Call Pattern

When tool calls are found, the server:
1. **Cleans** the response by removing all `[TOOL_CALL: ...]`, `[SEARCH: ...]`, `[WHATSAPP: ...|...]`, `[CADENCE_TRIGGER: ...]`, `[FETCH_URL: ...]` blocks
2. **Executes** each tool in order, collecting results
3. **Appends** to the message history:
   - `assistant`: the cleaned response (or "Let me process that request." if empty)
   - `user`: a follow-up message with all results and an explicit instruction to NOT output any more `[TOOL_CALL:]` blocks
4. **Re-calls** the LLM — the final response comes from this second call

## Error Handling

- **Malformed JSON** in `[TOOL_CALL: ...]` is silently skipped (pass)
- **Tool execution errors** return `"Error: {message}"` as the result string
- **ValueError** (lead/deal not found) returns a clear error message
- **Other exceptions** return `"Error executing {tool_name}: {str(e)}"`

## Current Tools (11 total)

| Tool | DB Operation | Arg Pattern |
|------|-------------|-------------|
| `update_lead` | PATCH lead fields | `lead_name, fields{field: value}` |
| `attach_to_deal` | Link lead→deal | `lead_name, deal_name` |
| `detach_from_deal` | Unlink lead | `lead_name` |
| `create_deal` | Create deal + optional lead | `org_name, stage, ...lead_name` |
| `update_deal` | PATCH deal fields | `deal_name, fields{field: value}` |
| `search_leads` | SELECT by name/company | `query` |
| `search_deals` | SELECT by org_name | `query` |
| `send_whatsapp` | WhatsApp via lead name | `lead_name, message` |
| `trigger_cadence` | Cancel + reschedule | `lead_name` |
| `web_search` | Tavily API | `query` |
| `fetch_url` | Tavily extract | `url` |

## Pitfalls

- **`.format()` KeyError**: The system prompt contains JSON examples with `{}` curly braces. Using `"".format()` on a string containing `{"tool": ...}` will fail because Python tries to interpret `{tool}` as a format placeholder. **Fix**: Split into `AGENT_SYSTEM_PROMPT_BASE` (has format vars like `{company}`) and `AGENT_TOOL_SCHEMA` (JSON examples, no format vars). Call `.format()` only on the base, then `+` concatenate the schema.
- **Re-call LLM re-generating tool calls**: If the Stage 2 re-call message just says "Tool execution results:..." the LLM may output another `[TOOL_CALL: ...]` block thinking it's supposed to continue. **Fix**: The follow-up message must explicitly say "Do NOT output any [TOOL_CALL:] blocks — the actions are already done."
- **Confirmation word gap**: The confirmation gate checks user messages against `confirmation_words = {"yes", "yeah", "sure", "confirm", "proceed", "do it", "go ahead", "please do", "go for it", "that's right", "correct"}`. Common affirmatives like "ok", "okay", "k", "kk", "yep", "absolutely" are NOT included. When a user responds with one of these, `is_confirmed` returns `False`, and Ava loops back to asking "Shall I proceed?" again — the tool never fires, but Ava's text response may still sound like it executed. **Fix**: Add these to `confirmation_words` in server.py. The lesson from production: "ok" is one of the most common affirmatives and its absence causes silent failures where the user thinks the action happened but it didn't.
- **Empty response_clean**: If the LLM outputs ONLY a `[TOOL_CALL: ...]` with no text around it, `response_clean` becomes empty string. The fallback `response_clean or "Let me process that request."` handles this.
- **Thread separation**: Each chat thread is an independent conversation. Tool calls modify the database globally — the effects are visible in all threads, but the conversation history is per-thread.
