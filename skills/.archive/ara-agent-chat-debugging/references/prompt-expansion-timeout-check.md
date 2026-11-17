# Prompt Expansion → Timeout Check

Every time you add behavioral rules to Ava's system prompt (new sections, more examples, additional constraints), the LLM response time increases. This is because DeepSeek processes more input tokens.

## The Pattern

```
Add rules to AGENT_SYSTEM_PROMPT_BASE (15K → 30K+ chars)
    ↓
DeepSeek response time increases (5-10s → 20-30s)
    ↓
Coaching handler's requests.post timeout (15s) fires
    ↓
ReadTimeoutError → No coaching response delivered to Greg
    ↓
Sidecar keeps "typing..." for 2+ minutes (keepalive pings)
    ↓
No response ever arrives — Greg waits indefinitely
```

## How to Check

After any significant prompt expansion, check the coaching handler timeout:

```bash
grep -n 'timeout=' /Users/greg/ara/server.py | grep requests
```

Expected output:
```
8710:            timeout=120,
```

If it's still `timeout=15`, increase to `timeout=120` at line 8710.

## Why 15s Was Too Tight

The prompt went from ~15K chars (basic identity + tools + simple rules) to ~30K+ chars (CRITICAL rule, Data Honesty, Lead Disambiguation, Action Approval, Error Handling Protocol, expanded personality, two-tier confirmation flow). Each new section adds ~500-2000 chars. DeepSeek V4 Flash takes roughly 1 second per 1000 tokens of input + generation. A 30K char prompt (~7.5K tokens) with a 300-token response takes 8-15 seconds baseline. During peak load or cold start, this spikes to 20-30 seconds.

## Incident Timeline (June 3, 2026)

During this session, multiple behavior rules were added:
- CRITICAL rule (~2000 chars)
- System prompt type fix note (~500 chars)
- Expanded Error Handling Protocol (~1500 chars)
- "via WhatsApp" handling note (~500 chars)
- Missing tool call explanation (~800 chars)
- Lead Disambiguation Rule (~600 chars)
- Action Approval Rule with examples (~800 chars)

Total prompt expansion: ~6,700 chars. Response time increased from ~8s to ~25s. The 15s timeout fired on the first real WhatsApp request at 6:26 PM. No message to Rajesh was sent, no coaching reply returned.

## The Fix

```
timeout=15  →  timeout=120
```

This is a safety net, not a target. Most responses still come back in 3-8 seconds. The 120s gives headroom for cold-start LLM calls and prompt-expansion spikes. Greg won't notice any difference in normal operation — the timeout just won't cut off slow responses anymore.

## Verification

After increasing the timeout, send a test message to Ava via WhatsApp. Check:
1. `/tmp/ara-error.log` — no ReadTimeoutError entries
2. Server output — `200` status from the agent_chat POST, not a timeout
3. WhatsApp — coaching response arrives within 20-30 seconds
