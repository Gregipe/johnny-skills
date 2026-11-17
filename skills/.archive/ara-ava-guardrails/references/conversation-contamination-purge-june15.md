# Conversation History Contamination — Message Purging Pattern (June 15, 2026)

## The Pattern

The LLM reads its OWN history from the coaching thread and pattern-matches past behaviors — even when those behaviors were hallucinations, bugs, or stale requests. This creates a self-reinforcing loop: past hallucination → LLM sees it in context → repeats the hallucination → more contamination in history.

## Three Types of Contamination

### 1. Hallucinated Assistant Responses
Ava generates a response with tool calls the user never asked for (e.g., "Daily Summary cron"). This response is stored in AgentChatMessage. On subsequent turns, the LLM reads its own hallucination and thinks "I should do this again."

**Fix:** Purge assistant messages that contain hallucinated actions from the coaching thread.

```python
# Find and delete
msg = db.query(AgentChatMessage).filter(
    AgentChatMessage.role == "assistant",
    AgentChatMessage.content.ilike("%daily summary%")
).delete()
```

### 2. Historical User Requests (Stale Context)
Greg legitimately asked for something days/weeks ago (e.g., "set a daily morning briefing"). That request is still in the 50-message context window. The LLM sees it and thinks "Greg wants a daily briefing — let me set it up."

**Fix:** Purge old user messages that contain stale requests no longer relevant.

```python
msg = db.query(AgentChatMessage).filter(
    AgentChatMessage.role == "user",
    AgentChatMessage.content.ilike("%daily summary%")
).first()
if msg: db.delete(msg)
```

### 3. Meta-Instruction Messages (Wrong Channel)
Greg sends messages MEANT for Johnny (Hermes) to Ava by mistake. These messages contain formatting instructions, code review requests, or system design notes. The LLM reads them and tries to parse them as CRM commands, pattern-matching keywords into hallucinated tool calls.

**Fix:** Purge user messages that are clearly meta-instructions.

```python
db.query(AgentChatMessage).filter(
    AgentChatMessage.role == "user",
    AgentChatMessage.content.ilike("%could you repeat the same formatting%")
    | AgentChatMessage.content.ilike("%could you please add the regional%")
).delete()
```

## Cleanup Checklist

1. **Query all contamination:** Search for keywords that trigger hallucination patterns (daily, briefing, cron, summary)
2. **Purge hallucinated assistant responses:** Delete any assistant messages that contain the hallucination text
3. **Purge stale user requests:** Delete old user messages that requested the thing the LLM keeps re-proposing
4. **Purge meta-instructions:** Delete messages clearly meant for a different agent/channel
5. **Cancel related ActionItems:** Find all pending/awaiting_approval items with contamination keywords → cancel
6. **Cancel related ScheduledActions:** Find all pending cron jobs with contamination keywords → cancel
7. **Verify context window:** Query the 50 most recent messages and confirm zero contamination hits
8. **Commit the purge:** `db.commit()` — don't forget this

## Evidence — June 15 Cleanup

Opened with 270+ messages, 64 containing contamination keywords. After targeted purging:
- 8 hallucinated assistant responses deleted
- 5 meta-instruction user messages deleted (Johnny messages sent to Ava)
- 1 stale user request deleted (June 9 "daily summary" voice note)
- 1 stale user question deleted ("Can you set cron jobs now")
- 7 hallucinated ActionItems cancelled + deleted
- 2 rogue ScheduledActions cancelled

Final: 263 messages, zero contamination in recent 50, zero non-terminal ActionItems.

## Verification

```python
recent50 = db.query(AgentChatMessage).filter(
    AgentChatMessage.thread_id == thread_id
).order_by(AgentChatMessage.created_at.asc()).limit(50).all()

contaminated = [m for m in recent50 
    if "daily" in m.content.lower() 
    or "briefing" in m.content.lower() 
    or "cron" in m.content.lower()]
assert len(contaminated) == 0, f"Still have {len(contaminated)} contaminated messages"
```

## Related

- `references/arun-matthew-contamination-june15.md` — the Arun Matthew hallucination cascade from conversation history poisoning
- `references/tool-description-priming-june15.md` — root cause of the Daily Summary pattern
