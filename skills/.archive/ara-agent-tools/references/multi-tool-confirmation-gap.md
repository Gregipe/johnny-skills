# Multi-Tool Confirmation Gap (June 17, 2026)

## The Problem

`_classify_confirmation` returns a single token: `confirm`, `reject`, or `unrelated`. When a pending ActionItem has MULTIPLE tool calls and the user partially confirms ("ignore X, just do Y"), the classifier maps "ignore" → `reject` and the rejection handler cancels the ENTIRE pending action — including the tool the user wanted.

## Real Incident

**Date:** June 17, 2026, 9:29 AM IST

**Sequence:**
1. Greg: "send a whatsApp message to Jimmie Tete and tell him that i will send the infosec today itself."
2. Ava proposed TWO tools: `create_deal` (Shriram Finance / Ajay Fageria) + `send_whatsapp` (Jimmie Tete)
3. Greg: "Ignore the shriram finance deal for now and just handle the whatsApp to Jimmie please."
4. Classifier input: PROPOSAL = "💰 Create deal: Shriram Finance — shall I create it?; 💬 Send WhatsApp to Jimmie Tete — ..." + REPLY = "Ignore the shriram finance deal..."
5. Classifier output: `reject`
6. Handler (line 6416): Set ActionItem `3bb54770` to `cancelled`, returned "Okay, cancelled — I won't make that change."
7. Result: WhatsApp to Jimmie was NEVER sent.

## Why "Ignore" → reject

The classifier prompt at line 365-376:
```
Rules:
- A short affirmative → confirm
- A short negative ("no", "cancel", "don't", "wait") → reject
- A NEW command/question → unrelated
```

"Ignore" was matched to the negative/reject bucket. The classifier has no concept of "reject part, confirm part."

## Architecture Limitation

The confirmation flow stores all tool calls as ONE ActionItem row. Confirmation is all-or-nothing per ActionItem. There's no mechanism to split a multi-tool pending action into "confirm these, reject those."

### Current rejection handler (line 6416-6426):
```python
elif _verdict == "reject":
    _live.execution_state = "cancelled"
    _live.status = "resolved"
    _live.outcome_state = "resolved"
    _live.resolved_at = datetime.utcnow()
    _ack = "Okay, cancelled — I won't make that change."
    # ... save messages, return
```

It never inspects `_live.pending_tool_calls` to see WHICH tools the user might still want.

## Mitigations

### Short-term (pre-confirmation): Tool-count guard
Before creating the pending ActionItem, check whether the LLM proposed more tools than the user's request warrants. If the user asked for ONE thing but the LLM proposed N>1 tools, either auto-trim to the matching tool or re-prompt: "You proposed N actions but the user only asked for 1. Which one matches their request?"

### Short-term (post-rejection): Parse for "just do X"
When the classifier returns `reject`, scan the user's reply for "just do X" / "handle Y" language. If found:
1. Extract which tool call(s) the user confirmed
2. Create a new pending ActionItem with only those tools
3. Execute immediately (user already confirmed)

### Long-term: Structured classifier output
Upgrade `_classify_confirmation` to return structured output for multi-tool proposals:
```json
{"verdict": "partial", "keep": [1], "reject": [0]}
```
Where indices map to the pending `tool_calls` array.

## Debugging Trace (June 17)

```bash
# 1. Check agent_chat_messages for the conversation
ssh root@46.224.132.99 "cd /opt/ara && python3 -c \"
import sqlite3; db = sqlite3.connect('ara.db')
rows = db.execute('SELECT role, substr(content,1,200), created_at FROM agent_chat_messages WHERE created_at > datetime(\"now\",\"-12 hours\") ORDER BY created_at DESC LIMIT 20').fetchall()
for r in rows: print(f'{r[2]} | {r[0]:10s} | {r[1][:150]}')
\""

# 2. Check pending ActionItems
ssh root@46.224.132.99 "cd /opt/ara && python3 -c \"
import sqlite3; db = sqlite3.connect('ara.db')
rows = db.execute('SELECT id, description, execution_state, pending_tool_calls, created_at FROM action_items WHERE created_at > datetime(\"now\",\"-12 hours\") ORDER BY created_at DESC LIMIT 10').fetchall()
for r in rows: print(f'[{r[3]}] {r[2]} | {r[1][:120]}')
\""

# 3. Check server logs for CONFIRM-FLOW
ssh root@46.224.132.99 "journalctl -u ara-server --since '...' --until '...' --no-pager | grep CONFIRM-FLOW"
```

## Related

- `ara-agent-tools` skill — Confirmation Gate section
- `ara-agent-chat-debugging` skill — Layer 3 (check what agent_chat received)
- `ara-ava-guardrails` skill — Pipeline injection over-generation pitfall (companion bug)
