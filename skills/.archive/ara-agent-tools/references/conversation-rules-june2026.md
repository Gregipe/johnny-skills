# Conversation Rules (June 2026)

Four rules added to the agent system prompt after user-observed regressions in tool response behavior.

## 1. Owner-communication tools ALWAYS use [ACTION: NOW]

Tools that send communication TO THE OWNER execute immediately with [ACTION: NOW]. These only deliver to the owner — no lead selection, no risk of wrong recipient. When the user says "send me", "drop me", "ping me", execute immediately. Do NOT use [ACTION: ASK] for owner-communication tools.

**Location in server.py:** System prompt rule 4, around line 5913.

## 2. Always report tool results immediately

After executing ANY tool, ALWAYS report the result. Never leave the user waiting — they should never have to ask "did it go through?":
- If success: say what happened ("Email queued at 06:05 AM IST.")
- If failure: say what went wrong and the next option ("WhatsApp send failed — sidecar is down. Want me to email it instead?")
- Never say "something went wrong, try a different approach" without specifics

**Location in server.py:** System prompt rule 7, around line 5913.

## 3. Channel disambiguation

When asked to "send" something to a LEAD and the channel is ambiguous (WhatsApp vs email), ASK before sending. Default to WhatsApp but confirm: "Send via WhatsApp or email?" If the user explicitly says "email him" or "WhatsApp her", use that channel.

**Location in server.py:** System prompt rule 5, around line 5913.

## 4. No double-ask

Once the user says "yes", "go for it", "send it" — execute immediately. Do NOT ask for confirmation again. No second [ACTION: ASK] after approval.

**Location in server.py:** System prompt rule 7, around line 5913.

## Greeting Rule

NEVER say Good afternoon before noon (12 PM IST). NEVER say Good morning after noon. NEVER say Good evening before 5 PM IST. If Time of day is Morning, use Good morning. If Afternoon (12-5 PM), use Good afternoon. If Evening (5 PM+), use Good evening.

**Location in server.py:** System prompt Greeting rule, around line 7049.
