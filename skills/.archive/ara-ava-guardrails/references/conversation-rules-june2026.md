# Conversation Rules — June 2026

Three guardrails added to Ava's system prompt to prevent recurring UX failures.

## 1. Greeting Enforcement

Ava must match the Time of Day label exactly.

**Rule in system prompt:**
```
NEVER say Good afternoon before noon (12 PM IST). NEVER say Good morning after noon. 
NEVER say Good evening before 5 PM IST. If Morning, use Good morning. 
If Afternoon (12-5 PM), use Good afternoon. If Evening (5 PM+), use Good evening.
```

**Bug fixed:** Ava said "Good afternoon" at 6:05 AM IST. Old rule only prohibited afternoon < noon and evening < 5 PM — left a gap for "morning" mislabeling as "afternoon." Added explicit mapping for all time ranges.

**Time-of-day computation (server.py):**
```python
if hour < 12:     _tod = "Morning"
elif hour < 17:   _tod = "Afternoon"
elif hour < 20:   _tod = "Evening"
else:             _tod = "Night"
```

## 2. Mandatory Result Reporting — No Silence After Execution

After executing any tool, Ava MUST report the result immediately in the same response.

**Rule in system prompt:**
```
After executing any tool, ALWAYS report the result immediately. If it succeeded, say what 
happened. If it failed, explain why and suggest alternatives. Never leave Greg waiting — 
he should never have to ask "did it go through?"
```

**Bug fixed:** Ava said "Let me resend that right away" then went completely silent. Greg had to ask "did you send it?" to receive confirmation. The tool executed but Ava never relayed the result.

## 3. Channel Disambiguation

When Greg says "send X to [lead name]," Ava must NOT silently assume WhatsApp.

**Rule in system prompt:**
```
When asked to "send" something to a lead and the channel is ambiguous, ASK which channel. 
Default to WhatsApp but confirm: "Send via WhatsApp or email?" Do NOT silently assume.
```

**Bug fixed:** Ava tried to send a PDF deck to Jimmie Tete via WhatsApp (which failed with a backend error) rather than asking Greg which channel he wanted.

## 4. Tool Error Recovery

When a tool fails, Ava must be specific and proactive — not vague.

**Rule in system prompt:**
```
When a tool fails, say exactly what went wrong and offer specific alternatives. 
Don't say "try a different approach" — say "WhatsApp send failed (backend error). 
Want me to email instead?"
```

**Bug fixed:** Ava said "Something unexpected happened. Can you try a different approach?" — too vague, wasted a turn.
