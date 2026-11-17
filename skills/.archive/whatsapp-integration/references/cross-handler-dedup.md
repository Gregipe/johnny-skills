# Cross-Handler Deduplication: forwardedMsgIds Set

## Problem

On WhatsApp reconnect (every ~50 min), Baileys fires two independent events for the same message:

1. **`messages.upsert`** — fires with recent messages from the chat history
2. **`chats.update`** — fires with the same chat's updated state

Both handlers independently call `sendToARA()`, sending the same message to ARA twice. Ava processes each independently, producing duplicate coaching responses.

## Symptom

- Two identical coaching responses sent within 1-3 seconds of each other
- Server logs show two `LID JID fallback: mapping owner reply to coaching` entries with the same message
- Sidecar logs show both `Self-chat DM:` (from `messages.upsert`) and `Self-chat detected via chats.update:` (from the second handler) for the same message ID

## Fix: `forwardedMsgIds` Set

```javascript
// ── State ──
const forwardedMsgIds = new Set(); // Track messages forwarded to ARA to avoid dupes
const FORWARDED_IDS_MAX = 5000;    // Cap to prevent unbounded growth

function trackForwarded(id) {
  if (!id) return;
  if (forwardedMsgIds.size >= FORWARDED_IDS_MAX) {
    // Clear oldest half when at capacity
    const toDelete = [...forwardedMsgIds].slice(0, FORWARDED_IDS_MAX / 2);
    for (const delId of toDelete) forwardedMsgIds.delete(delId);
  }
  forwardedMsgIds.add(id);
}
```

### In `messages.upsert` (self-chat DM + lead replies):

```javascript
// Dedup: skip if already forwarded by chats.update handler
if (forwardedMsgIds.has(msg.key.id)) {
  logger.info(`Skipped (already forwarded): msgId=${msg.key.id}`);
  continue;
}
trackForwarded(msg.key.id);
sendToARA(ownerPhone, 'Owner', text, true, msg.key.id, remoteJid);
```

### In `chats.update` (self-chat only):

```javascript
// Dedup: skip if already forwarded by messages.upsert handler
// IMPORTANT: trackForwarded is called BEFORE sendToARA so that the ID is
// already tracked when the other handler fires — prevents race condition.
const lastMsgId = lastMsg.key?.id;
if (lastMsgId) {
  if (forwardedMsgIds.has(lastMsgId)) {
    logger.info(`Chats.update skipped (already forwarded): msgId=${lastMsgId}`);
    continue;
  }
  trackForwarded(lastMsgId); // Mark NOW, before sendToARA
}
sendToARA(phone, 'Owner', text, true, lastMsg.key?.id || '', chat.id);
```

### In lead reply path (`messages.upsert`, non-fromMe):

```javascript
if (forwardedMsgIds.has(msg.key.id)) {
  continue;
}
trackForwarded(msg.key.id);
sendToARA(phone, pushName, text, false, msg.key.id, remoteJid);
```

## Key Design Decisions

1. **Global Set, not per-handler** — The whole point is to deduplicate *across* handlers, so the Set must be shared.
2. **Persists across reconnects** — Declared outside `startSocket()`. This means if the same old message ID comes through on a later reconnect, it's still skipped. Desired behavior.
3. **Capped at 5000 entries** — Clears oldest half when full. Message IDs are small strings (~24 chars), so 5000 entries is ~120KB — negligible memory.
4. **Checked BEFORE `sendToARA()`** — Avoids duplicate network calls. The check is at the decision point, not after the send.

## Testing

- Kill sidecar, send a WhatsApp message to self, restart sidecar — the message should be processed once
- Kill sidecar, send 2-3 messages to self, restart sidecar — recent messages (<15s) should each fire once, old ones (>15s) should be skipped by the backlog filter
