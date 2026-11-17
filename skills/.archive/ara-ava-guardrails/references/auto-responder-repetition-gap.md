# Auto-Responder Repetitive Message Gap

## The Problem

`_ava_auto_respond()` in server.py generates a unique LLM response for EVERY inbound message from a lead, with no detection of repetitive or low-effort content. This produces escalating auto-responses that make Ava look desperate.

## Observed Incident (June 4, 2026)

Rajesh Sharma's number received 6 messages in 3 minutes (21:45-21:48 IST) from test curls that hit the webhook:

| # | Inbound | Outbound |
|---|---------|----------|
| 1 | "test" | "Hey Rajesh! Got your test..." |
| 2 | "health check" | "All good on this end..." |
| 3 | "health check" | "Third health check confirmed..." |
| 4 | "health check" | "health check number four..." |
| 5 | "health check" | "keeping me on my toes..." |
| 6 | "health check" | "health check passed with flying colors again!" |

Each message got a progressively more desperate sales pitch despite being the same word repeated.

## Root Cause

- No content comparison with recent messages from the same lead
- No rate limit per lead
- The `AVA_AUTO_SYSTEM_PROMPT` has a strong action bias — she's told to "handle lead replies" and "move toward meeting booking," so she escalates each time

## Fix Deployed (June 4, 2026)

**Location:** `_handle_inbound_whatsapp()` in server.py, immediately after lead lookup and before logging the conversation.

**Mechanism:** Content-similarity gate using Python's `difflib.SequenceMatcher`:

```python
last_conv = db.query(Conversation).filter(
    Conversation.lead_id == lead.id,
    Conversation.direction == "inbound",
).order_by(Conversation.created_at.desc()).first()
if last_conv and last_conv.content and message:
    from difflib import SequenceMatcher
    similarity = SequenceMatcher(None,
        last_conv.content.strip().lower(),
        message.strip().lower()
    ).ratio()
    # Handle timezone-aware vs naive datetime
    last_time = last_conv.created_at
    if last_time:
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        time_since = (utcnow() - last_time).total_seconds()
    else:
        time_since = 999
    if similarity > 0.7 and time_since < 300:
        log.info(f"Repetitive message from {lead.name}: skipped")
        db.close()
        return  # Silently dropped — no log entry, no response
```

**Parameters:**
- Similarity threshold: 0.7 (70% — catches "health check" vs "health check again")
- Time window: 300 seconds (5 minutes)
- Matches only last message (not N-gram window — covers the common case without over-complicating)

**Verified:** Two identical "hello" messages 7 seconds apart. First triggered auto-response. Second got: `Repetitive message from Rajesh Sharma: "hello..." (sim=1.00, age=7s) — skipped`

## Testing Webhooks Safely

**Never use a real lead's phone number in test curls.** The webhook endpoint (`POST /api/whatsapp/inbound`) finds the lead by phone and triggers `_ava_auto_respond()` which sends a real WhatsApp message. Every curl to this endpoint with a real phone number results in a real message.

**Correct approach:** Create a test lead with a fake phone number (e.g., +919999999990) before running tests, or use the `/api/agent/chat/{tenant_id}` endpoint instead which doesn't send WhatsApp messages.

## Cross-Reference

- `ara-ava-guardrails` — Simple Questions Rule (same principle: don't over-respond). Pitfalls section covers the auto-responder gap.
- The fix sits at `_handle_inbound_whatsapp` level (before any conversation logging), not in `_ava_auto_respond` itself.
