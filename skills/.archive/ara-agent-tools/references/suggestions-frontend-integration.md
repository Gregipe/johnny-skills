### 6. Working Hours Constraints (Optional)

When tools fire at scheduled times (auto-emails, cadence messages), respect working hours:

```
WhatsApp/SMS → fire anytime (low intrusion)
Email/Call   → only 9AM-6PM weekdays (respect recipient's business hours)
Replies      → bypass all constraints (the lead engaged first, so it's urgent)
```

Implementation is channel- and trigger-context-specific — apply in the tool handler or scheduler, not in the core re-call loop.

### 7. Security: Prompt Injection Hardening

When building agent tools that accept external input (lead messages, user text), the system prompt must be hardened against prompt injection.

**Core principle:** Never interpolate user-controlled text into instruction sentences. Always place it in a clearly labeled data section with visible delimiters.

**See `references/action-agent-7-layer-expansion.md#security-hardening` for the full pattern, attack vectors, and fix applied.**

**Quick reference:**
- ❌ `- {lead_message} is the latest message` — inline injection, DANGEROUS
- ✅ `## The lead's latest message:\n<lead_message>\n{lead_message}\n</lead_message>` — labeled data with delimiters, SAFE
- User message should ALSO be sent as a separate `{"role": "user", "content": message}` — defense in depth

### 8. Contextual Suggestions (Optional)