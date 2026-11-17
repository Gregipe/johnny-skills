# Coaching Context + Confirmation Classifier Bugs (June 2026)

## Bug 1: `asc()` loads 50 oldest messages (causes hallucinations)

**Symptom:** Ava references leads and conversation topics from 3-6 weeks ago that were never in the current session. "Which one — Dinesh Nagar lead, the Ramgopal catchup, or both?" when neither was in the conversation.

**Root cause:** `/api/agent/chat/{tenant_id}` loads context with:
```python
recent_msgs = msg_query.order_by(AgentChatMessage.created_at.asc()).limit(50).all()
```
`asc()` gets the 50 OLDEST messages. For a thread with 1,324 messages, this loads May-June 16 conversations, injecting 3-week-old context into every prompt.

**Fix:** 
```python
recent_msgs = list(reversed(msg_query.order_by(AgentChatMessage.created_at.desc()).limit(50).all()))
```
Loads 50 most recent in chronological order. Location: ~line 7001 in server.py.

**Verification:** After fix, `DESC+reversed` window should span last 2 days (not 3 weeks):
```
OLD (asc, limit 50): May 25 — Jun 16
NEW (desc+rev, limit 50): Jun 22 — today
```

## Bug 2: Confirmation classifier misses "did you send it?" and "and?"

**Symptom:** After Ava proposes a WhatsApp send with `[ACTION: ASK]`, owner types "Did you send it yet?" or "and?". Classifier marks it as "unrelated" instead of "confirm" — Ava restarts the flow instead of executing.

**Root cause:** The confirmation classifier prompt in `_classify_pending_reply()` only lists "done?", "is it done?", "update?", "any update?", "what happened?", "did you do it?" as confirmation patterns. "Did you send it yet?" and "and?" are not in the list.

**Fix:** Add to the classifier prompt (line ~375 in server.py):
```
"- A status check that implies the proposal was expected to execute (\"done?\", \"is it done?\", \"update?\", \"any update?\", \"what happened?\", \"did you do it?\", \"did you send it?\", \"and?\") => confirm"
```

**Deeper issue:** The `send_whatsapp_to_owner` tool is always wrapped in `[ACTION: ASK]` by the system prompt (line 5865: "On confirmation, call ONLY send_whatsapp with [ACTION: NOW]"). This means send_whatsapp NEVER executes on first command — it always requires a confirmation roundtrip. If the classifier then misreads the confirmation, the flow breaks silently.

**Design tension:** The tool itself works perfectly when called directly (`wa.send_to_owner()`). The coaching pipeline's ASK/CONFIRM gating is the bottleneck — the tool fires instantly when bypassed, but the pipeline forces a fragile LLM-classified confirmation step.
