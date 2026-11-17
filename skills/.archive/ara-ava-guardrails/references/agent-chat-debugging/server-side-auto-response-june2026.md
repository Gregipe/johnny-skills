# Server-Side Auto-Response on Tool Success

Eliminating the second LLM call to prevent "glitch" narratives and speed up responses.

## Problem

After every tool execution, the server made a second LLM call to "synthesize" results. This caused:
- Narratives: LLM invents "glitch/hiccuped" framing for successful actions
- Stutter: Second call echoes response_clean text
- Latency: 3-8s extra per response
- Inconsistency: LLM sometimes ignores the "say it simply" follow-up instruction

## Architecture

```
Before:
User "send it" → LLM (generates [TOOL_CALL:]) → server executes tool → LLM (synthesizes) → "Done!"
                                                                          ^^^^^^^^^^^^^^^^^^
                                                                          This call invented narratives

After:
User "send it" → LLM (generates [TOOL_CALL:]) → server executes tool → "Done! Message sent. 🙌"
                                                                        ^^^^^^^^^^^^^^^^^^^^^^^^^
                                                                        No LLM involved
```

## Code Changes

### 1. Capture response_original at source (line ~5561)

```python
response = call_llm(messages)
response_original = response  # Preserve original (with tool calls) for DB storage
```

### 2. Save original to DB on not-confirmed path (~line 5633)

```python
if not is_confirmed:
    response = response_clean or "I can help with that."
    db_response = response_original  # Save original with tool call to DB
```

### 3. Use db_response when available (~line 5710)

```python
db.add(AgentChatMessage(tenant_id=tenant_id, role="assistant", 
    content=db_response if 'db_response' in dir() else response, 
    thread_id=thread_id))
```

### 4. Auto-response on success - pending_tools path (~line 5707)

```python
if errors:
    # LLM call: explain what went wrong
    follow_up = f"The tool returned: {result_summary}\n\nTell the user what happened..."
    messages.append({"role": "user", "content": follow_up})
    response = _call_llm(messages)
else:
    # No LLM call: return canned success
    lead_name = pending_tools[0].get("args", {}).get("lead_name", "")
    response = f"Done! Message sent to {lead_name}. 🙌"
```

### 5. Auto-response on success - normal tool path (~line 5745)

```python
if not errors:
    lead_name = next((args.get("lead_name") for _, args in tool_calls if "lead_name" in args), "")
    response = f"Done! Message sent to {lead_name}. 🙌"
```

### 6. Follow-up guard (~line 5726)

```python
if 'pending_tools' not in dir() or errors:
    # Only runs when: no pending_tools (normal flow), OR pending_tools had errors
    result_summary = "\n".join(results)
    ...
    response = _call_llm(messages)
```

## Edge Cases

- **Multiple tools, some failed:** Still make the second LLM call. The response should say what succeeded and what failed.
- **Tool returned unexpected but not error:** E.g. search_leads returned empty. The auto-response would say "Done! All set. 🙌" which is misleading. Fix: only auto-respond for send_whatsapp/send_email/schedule_message. For search/read tools, let the LLM synthesize.
- **Lead name not in args:** Fall back to "Done! All set. 🙌" instead of "Done! Message sent to . 🙌"

## When Still to Use the Second LLM Call

- Tool returned a non-error unexpected result (search found nothing)
- Multiple tools with mixed results
- User asked a question that requires tool results to answer
- Tool returned a warning that needs interpretation
