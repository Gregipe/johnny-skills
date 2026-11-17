# Ava Auto-Response Architecture

Architecture for Ava (autonomous SDR agent) responding to inbound WhatsApp messages from assigned leads.

## Flow Diagram

```
WhatsApp Keepalive Loop (every 30s)
  │
  └─ _check_inbound()
       │
       ├─ Query leads WHERE assigned_agent='ava'
       ├─ Build phone-number lookup (normalized, last-10-digits)
       ├─ Find unread chat indicators
       │
       └─ For each unread chat (max 3):
            ├─ Click to open
            ├─ Extract phone from URL (?phone=...)
            ├─ Match against known leads
            │
            ├─ NOT matched → skip silently
            │
            └─ MATCHED → call on_inbound_message(phone, name, message)
                              │
                              └─ _handle_inbound_whatsapp() [in server.py]
                                   │
                                   ├─ 1. Log inbound Conversation to DB
                                   ├─ 2. Check assigned_agent == 'ava'
                                   │
                                   ├─ NOT Ava → done (just logged)
                                   │
                                   └─ AVA → auto-response:
                                        ├─ Load recent conv history (last 4)
                                        ├─ Build AVA_AUTO_SYSTEM_PROMPT with lead context
                                        ├─ call_llm(messages, temperature=0.6)
                                        │
                                        ├─ LLM failed → log warning, skip
                                        │
                                        └─ LLM succeeded:
                                             ├─ wa.send_message_sync(phone, response)
                                             ├─ Send succeeded → log outbound Conversation
                                             └─ Send failed → log error
```

## Key Files

| File | Role |
|------|------|
| `server.py` | `AVA_AUTO_SYSTEM_PROMPT` definition, `_handle_inbound_whatsapp()` handler, callback registration |
| `whatsapp_manager.py` | `_check_inbound()` with `assigned_agent='ava'` filter, `_dispatch()` thread-safe bridge |
| `induction_engine.py` | `call_llm()` — shared DeepSeek LLM client for both induction and Ava responses |
| `database.py` | `Lead.assigned_agent` default changed from `'sdr'` to `'ava'` |

## Prompt Template

```python
AVA_AUTO_SYSTEM_PROMPT = """You are Ava, an AI Sales Development Representative
for {company} (via Hunar.ai).

## Your Role
- Responding to an INBOUND message from a lead
- Professional, warm, concise
- Always identify as Ava from {company}

## Rules
1. Answer clear questions directly and professionally
2. For ambiguous questions: "I'll check with my team and get back to you"
3. NO pricing, discount, feature promises
4. **Respond naturally** — as the conversation demands. If "sure" or "thank you" or "got it" is the right response, say that. Do NOT artificially pad responses to make them longer.
5. Don't loop in Greg in your response — handle it or defer gracefully

## Lead Context
Lead Name: {lead_name}
Company: {lead_company}
Stage: {lead_stage}
...
```

## Error Recovery

| Failure | Behavior |
|---------|----------|
| LLM returns error ("⚠️...") | Skip auto-response, log warning. No message sent. |
| WhatsApp send fails | Log error. Outbound Conversation NOT saved (avoids phantom records). |
| DB connection fails | Handler catches exception, logs it, returns silently. Inbound message may not be logged. |
| Lead not found by phone/name | Drop silently — logged at WARNING level for debugging. |

## Thread Safety Notes

- `_handle_inbound_whatsapp()` runs on the WhatsApp keepalive thread (daemon thread).
- `wa.send_message_sync()` uses `asyncio.run_coroutine_threadsafe()` to dispatch work to the WhatsApp event loop thread.
- New DB sessions are created per handler call — no session reuse across callbacks.
- All exceptions are caught at the handler level — a failure in auto-response doesn't crash the keepalive loop.
