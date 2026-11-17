# Tool Execution UX: Async Visibility (June 2026)

## The Complaint

Greg (June 2026): "I have no idea if it's checking, if it's going to reply, or if it's done."

When a tool call takes time (read_logs, web_search, generate-prompt), the dashboard shows only a loading spinner. The user has no visibility into:
1. **What the system is doing** — is it checking logs? Running a query? Waiting on an API?
2. **Whether it's going to reply** — is the spinner indefinite or bounded?
3. **Whether it's done** — did the tool succeed? Fail? Time out?

## The Approval Workflow Confusion

When Ava proposes a tool call (e.g., `trigger_cadence`), the response shows:
```
[PENDING - awaiting your confirmation]
[TOOL_CALL: {"tool": "trigger_cadence", "args": {"lead_name": "Gregory Ipe"}}]
```

The user sees this and asks **"Has it started?"** instead of confirming (saying "send it" or "yes"). This triggers a cascade:

1. The server sees "Has it started?" as a new user message
2. Ava interprets it as a question about status → calls `read_logs`
3. `read_logs` finds nothing (because the trigger was never confirmed)
4. Ava reports nothing useful back to the user

**The UX failure:** The user doesn't know they need to confirm. The "[PENDING]" prefix is text — it doesn't look like a prompt for action. A button, a yes/no indicator, or a more explicit instruction ("Say 'send it' to confirm") would make this clear.

## Patterns That Help

### Add interim status messages
When a tool call will take >5s (read_logs, web_search, long LLM calls), send an interim message:
```python
wa.send_to_jid(COACHING_GROUP_JID, "Checking server logs...")
wa.send_to_jid(COACHING_GROUP_JID, "Running trigger_cadence now...")
```

The "Ava is thinking..." pattern already exists in the enforcer block. But it's not universal — many slow paths lack any interim message.

### Label the lazy spinner
If the dashboard shows a spinner during tool execution, change it to include what's happening:
```
Ava is checking the logs...
Ava is running the outbound sequence...
```
This turns a scary "is it broken?" wait into a "I know what's happening" wait.

### Make pending confirmation explicit
Instead of just `[PENDING - awaiting your confirmation]`, add:
```
**Say "send it" to execute this, or tell me to change it.**
```
Right after the tool call. The user needs to know what action THEY need to take.

### Guard against the log-check rabbit hole
When the user asks "Has it started?" about a pending tool call, Ava should detect the pending state and respond directly rather than pivoting to read_logs:

```python
# After receiving user message, before agent_chat:
_has_pending_tool = any(
    "[PENDING" in m.content for m in recent_msgs[-3:]
    if m.role == "assistant"
)
if _has_pending_tool:
    # Instead of calling LLM, respond directly about the pending action
    response = "This action is awaiting your confirmation. Say 'send it' or 'yes' to execute, or let me know what you'd like to change."
```

This prevents the "Has it started?" → read_logs → nothing found → user frustrated loop.

## References

- `ara-agent-chat-debugging` — The full pending confirmation flow architecture
- `ara-agent-chat-debugging/references/server-side-auto-response-june2026.md` — The server-side auto-response pattern for confirming tool calls
- `ara-ava-guardrails` — The approval workflow rules and confirmation patterns
