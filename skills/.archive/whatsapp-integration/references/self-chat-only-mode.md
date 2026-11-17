# Self-Chat-Only Mode (June 2026)

## Decision

As of June 1, 2026, the sidecar processes **only self-chat messages** (the owner messaging themselves). Groups, lead replies, and personal DMs are all dropped at the sidecar level.

## Rationale

- Owner only wants coaching via self-chat — no lead auto-reply, no group monitoring
- Prevents Ava from accidentally replying to personal contacts or group members
- Simpler code path: no need to distinguish leads from non-leads at the sidecar level
- No risk of group messages leaking through to ARA (previous bug: @lid groups not matching @g.us filter)

## What Gets Dropped

| Source | What happens | Log line |
|--------|-------------|----------|
| Group messages (any @g.us or @lid group) | `@g.us` check at top of messages.upsert loop | No log (early `continue`) |
| Owner DM to personal contact | `isFromMe` DM handler → `!isSelfChat` → `continue` | `Owner DM to {jid}: skipped (not self-chat)` |
| Inbound from non-owner (lead or friend) | `else` branch → `continue` | `Inbound from {name}: skipped (not self-chat)` |
| Owner self-chat | Full processing: backlog filter → dedup → sendToARA | `Self-chat DM: "..."` |

## Where the Filters Live

All in `whatsapp-sidecar/index.js`:

1. **`messages.upsert`** — primary handler. `@g.us` check, then `isSelfChat` check for `isFromMe`, else branch for non-owner
2. **`chats.update`** — fallback handler. Same `@g.us` check + `isSelfChat` check + backlog filter + forwardedMsgIds dedup

## If Lead Replies Need to Be Re-enabled

Restore the `else` branch in `messages.upsert`:

```javascript
} else {
  sendToARA(phone, pushName, text, false, msg.key.id, remoteJid);
}
```

And remove the `@g.us` skip if group processing is also needed. This was the original behavior before June 1, 2026.
