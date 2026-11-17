# WhatsApp Reconnect Dedup — June 2026

## Problem

Every ~50 minutes, WhatsApp WebSocket disconnects (server-side timeout). When Baileys auto-reconnects, it fires TWO events for the same chat messages:

- `messages.upsert` — delivers recent messages from the conversation
- `chats.update` — delivers updated chat state

Both handlers independently called `sendToARA()` on the server, triggering Ava to respond twice to the same user query.

## Root Cause

No cross-handler coordination. The `messages.upsert` handler and `chats.update` handler were independent — each had its own 15-second backlog filter, but no shared state preventing them from both forwarding the same message.

## Fix Applied

**File:** `whatsapp-sidecar/index.js`

Added a `forwardedMsgIds` Set that tracks every message ID forwarded to ARA. Both handlers check it before sending:

```javascript
const forwardedMsgIds = new Set();

// With a cleanup cap (prevents unbounded growth):
const FORWARDED_IDS_MAX = 5000;
function trackForwarded(id) {
  if (!id) return;
  if (forwardedMsgIds.size >= FORWARDED_IDS_MAX) {
    const toDelete = [...forwardedMsgIds].slice(0, FORWARDED_IDS_MAX / 2);
    for (const delId of toDelete) forwardedMsgIds.delete(delId);
  }
  forwardedMsgIds.add(id);
}
```

**In `messages.upsert` handler** (both self-chat and lead reply paths):
```javascript
if (forwardedMsgIds.has(msg.key.id)) {
  logger.info(`Skipped (already forwarded): msgId=${msg.key.id}`);
  continue;
}
trackForwarded(msg.key.id);
```

**In `chats.update` handler:**
```javascript
if (lastMsg.key?.id && forwardedMsgIds.has(lastMsg.key.id)) {
  logger.info(`Skipped (already forwarded): msgId=${lastMsg.key.id}`);
  continue;
}
if (lastMsg.key?.id) trackForwarded(lastMsg.key.id);
```

## Additional Fixes Applied (Same File)

| Fix | What Changed | Why |
|-----|-------------|-----|
| `keepAliveIntervalMs: 15000` | 30000 → 15000 | More aggressive pings to reduce disconnect frequency |
| `syncFullHistory: false` | true → false | Don't replay entire chat history on reconnect |
| `forwardedMsgIds` Set | New | Cross-handler dedup |
| Backlog filter in `messages.upsert` | New | Skip self-chat messages >15s old on reconnect |
| Backlog filter in `chats.update` | New | Skip chats.update messages >15s old on reconnect |
| `sentMsgIds` tracking | New | Track messages sent by sidecar to avoid echo |

## Files Modified

- `whatsapp-sidecar/index.js` — full rewrite with all fixes

## Verification

- Wait for the 50-min disconnect or trigger it manually (kill the sidecar)
- Send a WhatsApp message during the disconnect window
- When the sidecar reconnects, only ONE Ava response should arrive
- Check sidecar logs for `(already forwarded): msgId=...` messages
