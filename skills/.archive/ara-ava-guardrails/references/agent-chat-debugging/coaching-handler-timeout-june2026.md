# Coaching Handler Timeout — June 3, 2026

## The Bug

The `_handle_owner_coach_whatsapp` function in server.py calls `requests.post` to the internal `agent_chat` endpoint with a 15-second read timeout. With the expanded system prompt (30K+ chars from behavioral rules, lead context, tool schemas), DeepSeek LLM calls routinely take 20-30 seconds. The timeout fires before the LLM returns.

## Symptom

1. Owner sends a WhatsApp message to Ava (e.g., "send Rajesh a message...")
2. Sidecar processes it, calls `_handle_owner_coach_whatsapp`
3. `requests.post` fires with `timeout=15`
4. LLM call takes >15 seconds → `ReadTimeout: HTTPConnectionPool Read timed out. (read timeout=15)`
5. The except block catches the timeout but doesn't send a fallback response to the owner
6. Sidecar keeps showing "typing..." for 2+ minutes because:
   - The sidecar is still receiving keepalive pings (it's in a background thread that's still running)
   - The background thread has no mechanism to stop the typing indicator after the timeout
7. No coaching response ever arrives. The message to the lead is never sent.

## Error Log Pattern

```
Request: POST /api/agent/chat/3e736242 ... body-> send Rajesh a message
...
ReadTimeoutError: HTTPConnectionPool(host='localhost', port=8766): Read timed out. (read timeout=15)
Typing keepalive ping -> 200  (repeats every 2 seconds for 2+ minutes)
```

## The Fix

Line 8710 in server.py:
```python
# Was: timeout=(15, 15) — too tight for expanded prompt
# Now: timeout=120 — allows 2 minutes for DeepSeek to process
resp = requests.post(
    f"http://localhost:8766/api/agent/chat/{TENANT_ID}",
    json={"message": message, "thread_id": thread.id},
    timeout=120,
)
```

## Why It's Now 120 Seconds (Not 30 or 60)

The expanded system prompt triggers:
- DeepSeek's first-token latency (processing 30K+ tokens of context)
- The LLM-based intent detection call (additional LLM call for CONFIRM/REJECT)
- The re-call loop (when tools are executed and the LLM needs to synthesize)

In testing, the longest observed response was ~45 seconds. 120 seconds gives generous headroom for:
- Occasional DeepSeek API slowness
- Multiple tool calls in one turn
- The intent detection sub-call

## Did This Ever Hit Before?

Before the June 2026 behavioral rules (CRITICAL rule, Action Approval, etc.), the system prompt was much shorter (~15K chars). The LLM call usually returned in 5-10 seconds. The behavioral rules roughly doubled the prompt size, pushing response time past the old 15-second threshold.

## Files Modified

- `server.py` line 8710: `timeout=15` → `timeout=120`

## Related

- `ara-agent-tools/references/action-workflow-rules-june2026.md` for the behavioral rules that expanded the prompt
- `ara-ava-guardrails/references/server-side-auto-detection.md` for the auto-detection patterns added
