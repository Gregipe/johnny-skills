# Pre-Execution Enforcer & Metacognition Layer Design — June 2026

## Where the Code Lives

All in `server.py`, `agent_chat()` function.

### Pre-Execution Enforcer (line ~5353)

Inserted after the Stage 1 try/except block, before `# Parse tool calls from Ava's response`.

```python
_data_keywords = {"update", "change", "correct", "fix", "add", "create", "save", "set",
                   "schedule", "remind", "delete", "remove", "move", "send",
                   "email", "phone", "name", "stage", "cron"}
_msg_lower = user_msg.lower()
_has_intent = any(kw in _msg_lower for kw in _data_keywords)
_has_tool = "[TOOL_CALL:" in response
if _has_intent and not _has_tool:
    logging.getLogger("ara").warning(...)
    _enforcer_prompt = (
        "Your previous response described a data change but did NOT include a [TOOL_CALL:] block.\\n"
        "The user asked you to DO something that modifies data.\\n"
        f"User message: {user_msg}\\n\\n"
        "You MUST include the appropriate [TOOL_CALL:] block to actually execute.\\n"
        "Do NOT just describe what you would do - CALL the tool.\\n"
        "Try again with a tool call:"
    )
    messages.append({"role": "user", "content": _enforcer_prompt})
    try:
        response = call_llm(messages, model=_chat_model)
    except Exception:
        logging.getLogger("ara").error("Pre-execution enforcer re-call failed")
```

### Model Routing (line ~5277)

Inserted before Stage 1 LLM call, after `from induction_engine import call_llm`.

```python
_model_routing_keywords = {
    "email", "phone", "name", "stage", "notes", "company", "deal", "lead",
    "update", "change", "correct", "fix", "add", "create", "save", "set",
    "schedule", "remind", "evaluate", "qualify", "analyze", "research", "compare",
    "search", "move", "status", "stage"
}
_msg_words = set(user_msg.lower().split())
_use_pro = bool(_msg_words & _model_routing_keywords)
_chat_model = "deepseek-v4-pro" if _use_pro else "deepseek-v4-flash"
logging.getLogger("ara").info(
    f"Model routing: user_msg_keywords={_use_pro}, model={_chat_model}, msg_preview={user_msg[:60]}"
)
```

### Metacognition Prompt Rules (line ~5112)

Added to `AGENT_SYSTEM_PROMPT_BASE` after the CRITICAL tool-call rule:

```
- **When you cannot fulfill a request** (no matching tool, or all attempts failed):
  1. Say what happened clearly: *"I checked my tools, but I don't have a way to X yet."*
  2. Log the capability gap using [TOOL_CALL: log_capability_request].
  3. Offer the best workaround you CAN do with existing tools.
  4. Ask if they want the workaround, or if the answer above is sufficient.
  Example: *"I can't monitor for dormant leads automatically, but I can set a daily 9 AM check-in to scan for them. I've also logged this as a feature request. Want me to set that up?"*
```

### `log_capability_request` Tool (line ~4787)

Inserted after `log_insight` in the `execute_tool()` dispatcher. Creates an ActionItem with `action_type="capability_request"`.

Args: `user_request`, `missing_capability`, `attempted_tool`, `workaround`.

### `set_cron` Tool (line ~4597)

Inserted after `create_action_item` in `execute_tool()`.

Args: `title`, `frequency` (daily/weekdays/weekly), `time` (HH:MM), `message`, `action_type` (default: whatsapp_to_owner).

Creates a ScheduledAction with cron config in payload. First occurrence computed from current time + frequency.

### Scheduler Cron Reschedule Logic (line ~8139)

Modified the success handler in `_run_scheduler()`. After `_execute_action()` returns `True`, checks `action.payload.get("cron")`. If present, computes next `scheduled_at` based on frequency, sets status back to `"pending"` instead of `"completed"`.

## Key Design Decisions

| Decision | Reasoning |
|----------|-----------|
| **99% = tool call path** | Only Ava's response text is non-deterministic. Everything below is deterministic code paths. |
| **Pre-execution enforcer runs once** | One re-call attempt, then accepts whatever comes back. Doesn't block forever. |
| **Capability requests are ActionItems** | Same DB model as todos and reminders. I can query them with a simple SQLite call. |
| **set_cron uses payload JSON, not schema migration** | Avoids ALTER TABLE on a production DB. Cron config is ephemeral config, not relational data. |
| **95/5 split as a metric** | If >5% of requests trigger the metacognition path, the toolset is incomplete. This is the signal to build. |

## Phase 2 (Future)

- Timeout / rate limiting on the metacognition loop
- User abort / steering during interim processing
- Dedup identical capability requests from different users
- Dashboard to view capability request queue
