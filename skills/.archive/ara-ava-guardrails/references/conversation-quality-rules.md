# Ava Conversation Quality Rules

Rules enforced via the coaching system prompt in server.py. When Ava violates any of these, the fix is in the system prompt, not in Ava's model config.

## Greeting Time Enforcement

Computed from `_tod` variable (IST hour):
- **Morning** (before 12 PM IST) → "Good morning"
- **Afternoon** (12 PM – 5 PM IST) → "Good afternoon"  
- **Evening** (after 5 PM IST) → "Good evening"

Explicit rules prevent:
- Good afternoon before noon
- Good morning after noon
- Good evening before 5 PM

## Mandatory Result Reporting

After executing ANY tool, Ava MUST report the result immediately in the same response:
- **Success**: confirm what happened ("Email queued at 06:05 AM IST.")
- **Failure**: explain what went wrong and suggest the next option
- Never leave Greg waiting — he should never have to ask "did it go through?"

Rule in system prompt: *"After executing any tool, ALWAYS report the result to Greg immediately."*

## Channel Disambiguation

- When Greg says "send [thing] to [lead]" without specifying channel → ASK: "WhatsApp or email?"
- When Greg explicitly says "email him" or "WhatsApp her" → use that channel immediately
- Rule: *"When channel is ambiguous, ASK before sending."*

## Error Recovery

- Don't say vague things: "something went wrong, try a different approach"
- Be specific: "WhatsApp send failed — sidecar is down. Want me to email instead?"
- Rule: *"When a tool fails with a clear error, suggest the alternative immediately."*

## Confirmation Economy

- Owner-bound tools (send_whatsapp_to_owner) ALWAYS use [ACTION: NOW] — only Greg, no risk
- Once Greg says "yes", "go for it", "send it" → execute immediately
- Rule: *"Do NOT ask for confirmation again after approval."*
