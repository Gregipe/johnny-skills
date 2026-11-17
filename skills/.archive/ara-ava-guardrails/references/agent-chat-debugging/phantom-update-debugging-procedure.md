# Phantom Update Debugging Procedure

How to trace and fix "Ava said she updated X but the DB wasn't changed."

## The Signature

The assistant message in `agent_chat_messages` says something like "I've updated X's email to Y" but contains NO `[TOOL_CALL: update_lead]` block. The DB still has the old value.

## Step-by-Step Investigation

### 1. Check what Ava actually said (DB)

```sql
SELECT id, role, created_at, content FROM agent_chat_messages
WHERE created_at BETWEEN 'YYYY-MM-DD HH:MM:00' AND 'YYYY-MM-DD HH:MM:00'
ORDER BY created_at;
```

Look for the assistant response. If it says "I've updated X" but has no `[TOOL_CALL:` substring — that's the hallucination.

### 2. Count LLM calls (server logs)

```bash
journalctl -u ara-server --since "HH:MM:30" --until "HH:MM:45" | grep "POST https://api.deepseek.com"
```

- **2 calls** = main LLM + intent detector. The main call might have had `[TOOL_CALL:]` that got rejected by the confirmation gate.
- **1 call** = LLM generated text-only response (no tool call). The `if tool_calls:` block was never entered. This is the phantom update pattern.
- **3+ calls** = normal (main + detector + tool execution follow-up)

### 3. Reconstruct the LLM's context

Query the last 20 messages for the coaching thread at the time of the incident:

```sql
SELECT role, substr(content, 1, 120) as msg_preview, created_at
FROM agent_chat_messages
WHERE thread_id = (
    SELECT id FROM chat_threads
    WHERE tenant_id = '3e736242' AND thread_type = 'coaching'
    ORDER BY updated_at DESC LIMIT 1
)
ORDER BY created_at DESC LIMIT 20;
```

Key question: did the LLM see a previous "✅ Updated" assistant message that made it think the data was already correct? If the history shows a previous tool-execution response (like "✅ Updated Sahib Singh: phone → ...") and then the user sends a correction, the LLM may conflate the two updates.

### 4. Check the specific tool execution path

If the incident involves a voice message, check three things:

```python
# a) Did the voice guard fire correctly?
# Look at lines 5409-5425 in server.py for the 🎤 guard
# It should short-circuit the intent detector for data dictation

# b) Did the LLM actually generate a tool call?
# Check response_original (raw LLM output) in the DB
# The DB saves response_original for not-confirmed paths

# c) Did the post-processing check catch it?
# Search server logs for "Phantom update detected"
```

### 5. Verify the fix

After applying a fix:

1. Create a test lead with a known-wrong value
2. Dictate via voice: "The email is wrong, it's correct-spelling@domain.com"
3. Check the DB assistant message — must contain `[TOOL_CALL: update_lead` 
4. Check the DB lead record — must show the corrected value
5. Check server logs for "Phantom update detected" — should NOT appear (means the fix worked at the prompt level)

### Common Patterns

| Pattern | LLM calls | DB assistant msg | Root cause |
|---------|-----------|-----------------|------------|
| First-turn drop | 2+ (main + detector) | Has `[TOOL_CALL:]` | Confirmation gate rejected; user didn't confirm |
| Follow-turn hallucination | 1 (main only) | No `[TOOL_CALL:]` | LLM said "done" without calling tool |
| Voice guard bypass | 2+ (main + detector skipped) | Has `[TOOL_CALL:]` but wrong args | Voice guard didn't fire; intent detector said CONFIRM |
| Malformed JSON | 1 (main only) | Has `[TOOL_CALL: ...]` but unparseable | LLM generated tool call with bad JSON syntax |
