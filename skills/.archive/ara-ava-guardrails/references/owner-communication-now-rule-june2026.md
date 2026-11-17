# Owner Communication Rule — June 2026

## Problem

Ava's system prompt forced `[ACTION: ASK]` for ANY data-modifying tool, including `send_whatsapp_to_owner`. This meant Greg asking "drop me a WhatsApp" resulted in a confirmation gate ("reply yes to confirm"). The confirmation classifier then failed to recognize follow-ups like "Did you send it yet?" or "and ??" as confirmations, leaving Ava stuck in a loop.

## Root Cause

The prompt rule was:
```
"4. Direct-command exception: if the user gives the exact message to send — that's permission"
```

This was too narrow. It only covered the case where the user provides the exact text. "Drop me a message with pending actions" didn't match this — Ava interpreted it as needing confirmation before constructing the summary.

Meanwhile, Johnny bypassed the entire pipeline by calling `wa.send_to_owner()` directly — no confirmation gate, instant delivery. The inconsistency was confusing and frustrating.

## Fix: Platform-Agnostic Owner Communication Rule

Replaced the tool-specific rule with a general principle:

> **"Tools that send communication TO THE OWNER (e.g., send_whatsapp_to_owner, or any future owner-notification tool) ALWAYS use [ACTION: NOW]. These only deliver to Greg himself — no lead selection, no risk of wrong recipient. When the user says 'send me', 'drop me', 'ping me', or asks for a message/notification for themselves — execute immediately. Do NOT use [ACTION: ASK] for owner-communication tools."**

## Why This Is Safe

`send_whatsapp_to_owner` is guarded by `wa.send_to_owner()` which only sends to Greg's admin phone (919582549236), validated against the database on every call. There is zero risk of wrong-recipient. Confirmation adds friction without adding safety.

## Key Design Principle

Any tool whose destination is hardcoded to the owner should bypass confirmation. Confirmation gates exist to prevent wrong-recipient errors or destructive data changes — neither applies when the target is Greg's own phone.
