# Self-Chat Detection via `chats.update` (Baileys Multi-Device)

## The Problem

Owner replies to "Ava: ..." messages sent via WhatsApp self-chat (the owner's own number) are **not reliably detectable** via either Baileys event path. Two independent failure modes:

## Root Cause

When the sidecar is authenticated as the **owner's own WhatsApp account**, messages the owner sends to their own number (self-chat / "Note to Self") have two possible delivery paths depending on Baileys' LID state:

### Pre-LID Behavior (legacy — occurs when @s.whatsapp.net format is used)

Messages arrive through `chats.update` events (Baileys never fires `messages.upsert` for self-chat without LID). The `chats.update` handler checks `lastMessage` timestamp and `fromMe` flag to detect new self-chat messages. This path is **unreliable** — the `lastMessage` field is often absent from the update payload.

### Post-LID Behavior (default — occurs when @lid format is used)

**NEW FINDING (June 2026):** When Baileys transitions to LID format (after `syncFullHistory: true` history sync completes):

1. **`messages.upsert` DOES fire for self-chat** — the message arrives with `fromMe=true` and `remoteJid` in `@lid` format. The message is detected but **filtered out by the self-chat guard** because the guard compares against `{digits}@s.whatsapp.net` which never matches `@lid`.

2. **`chats.update` does NOT fire at all** — 0 entries observed across 870+ log lines. The `chats.update` handler for self-chat detection is a dead path when LID is active.

3. **`sock.user.id` remains in phone format** (`919582549236:82@s.whatsapp.net`) — the LID is only used for `remoteJid` in `messages.upsert`, not for the socket user identity.

**Result in both cases:** Owner gets no 👍 reaction, no typing indicator, and no Ava response when messaging themselves. The self-chat coaching flow is effectively broken with modern Baileys.

## Preferred Fix: WhatsApp Group (Not Self-Chat)

**Do not attempt to make self-chat work.** The reliable approach is to use a WhatsApp group instead. See `references/group-coaching.md` for the full implementation.

Self-chat detection via `chats.update` is documented below as a fallback, but it is **unreliable** — the `lastMessage` field is often absent from the update payload, and real-world testing shows it does not work consistently.

### LID-Format Real-World Confirmation (June 1, 2026 — Different Outcome)

Attempted a second self-chat coaching test on June 1, 2026 (different sidecar session with LID format active):

1. ARA sent "Ava: ..." message to owner's own number via `sendToJid(...)`
2. Message appeared on the owner's phone
3. Owner replied in self-chat: "Checking in on this?"
4. `messages.upsert` DID fire — with `remoteJid=37039848317007@lid` and `fromMe=true`
5. Debug logs confirmed message was caught by the `isFromMe` DM handler
6. **Self-chat guard dropped it:** `"Owner DM to 37039848317007@lid: skipped (not self-chat)"`
7. No `chats.update` events fired (0 entries in 870+ log lines)
8. Result: Owner got no response

**Key difference from pre-LID session:** With LID format, `messages.upsert` catches the self-chat message but the guard (`isSelfChat` check) blocks it because `remoteJid` is `@lid` and the guard builds a `@s.whatsapp.net` comparison JID.

**This confirms:** Self-chat coaching is broken in BOTH pre-LID and LID modes, for different reasons:
- Pre-LID: `messages.upsert` doesn't fire, `chats.update` unreliable
- LID: `messages.upsert` fires but guard blocks it, `chats.update` doesn't fire

**The only reliable path is the WhatsApp group.**

## The Fix: `chats.update` Handler

The `Baileys wiki` explicitly states: `chats.update` is "triggered on every message (to change the unread count), and to put the latest message / latest message timestamp in the chat object." This includes self-chat messages.

### Implementation Pattern

```javascript
// ── State: track last known state per JID ──
const chatTimestamps = new Map(); // JID -> { timestamp, unreadCount }

// ── Chat updates handler ──
sock.ev.on('chats.update', (chats) => {
  for (const chat of chats) {
    if (!chat.id || !chat.id.endsWith('@s.whatsapp.net')) continue;

    const phone = chat.id.replace('@s.whatsapp.net', '').replace(/[^0-9]/g, '');
    if (!phone) continue;

    // Extract last message from the chat update
    const lastMsg = chat.lastMessage || chat.conversation?.lastMessage;
    if (!lastMsg) continue;

    const text = getMessageText(lastMsg);
    if (!text) continue;

    // Compare with tracked state to detect genuinely new messages
    const prev = chatTimestamps.get(chat.id) || { timestamp: 0, unreadCount: 0 };
    const newTimestamp = (lastMsg.messageTimestamp || 0) * 1000;
    const newUnread = chat.unreadCount ?? prev.unreadCount;

    const isNewMessage = newTimestamp > prev.timestamp ||
      (chat.unreadCount !== undefined && newUnread > prev.unreadCount);

    if (!isNewMessage) continue;

    chatTimestamps.set(chat.id, { timestamp: newTimestamp, unreadCount: newUnread });

    // Skip echo from our own sends
    if (sentMsgIds.has(lastMsg.key?.id)) continue;

    // Only catch fromMe (self-chat) messages here — non-fromMe handled by messages.upsert
    if (!lastMsg.key?.fromMe) continue;

    logger.info(`Self-chat detected via chats.update: "${text.substring(0, 60)}..."`);
    sendToARA(phone, 'Owner', text, true, lastMsg.key?.id || '', chat.id);
  }
});
```

### Key Design Decisions

1. **Track `chatTimestamps` per JID** — Stores the last known `messageTimestamp` (converted to ms) and `unreadCount` for each chat JID. Without tracking, every `chats.update` event would trigger a false positive (the event fires even for presence/status changes).

2. **Two detection signals** — New message detected when:
   - Timestamp is higher than previously seen (primary signal)
   - `unreadCount` increased from previously seen (fallback for reconnection spikes)

3. **`lastMessage` extraction** — The `chats.update` event may have `lastMessage` at the top level or nested under `conversation.lastMessage`. Check both.

4. **Echo filter** — Messages sent by the sidecar via `/send` are tracked in `sentMsgIds`. The `chats.update` handler also checks this set to avoid re-processing own sends from the chat update path.

5. **Only `fromMe` messages** — The `chats.update` handler only processes `fromMe: true` messages (self-chat). Non-self-chat messages are already handled by the `messages.upsert` handler's existing pipeline.

### Timing

- `chats.update` fires **within 1-5 seconds** of the owner sending a self-chat message
- This is slightly slower than `messages.upsert` (which is near-instant for non-self-chat) but comparable to the owner's perception of "I sent a message and it appeared on the other device"
- On reconnection, `chats.update` fires for ALL recent chats — the `chatTimestamps` map handles this by only processing genuinely new messages (higher timestamp)

## Helper Functions Used

The sidecar uses two shared helpers to reduce duplication:

```javascript
function sendToARA(phone, name, message, ownerReply, msgId, remoteJid) {
  const payload = JSON.stringify({
    phone, name, message,
    owner_reply: ownerReply,
    message_id: msgId || '',
    remote_jid: remoteJid || `${phone}@s.whatsapp.net`,
  });
  // HTTP POST to ARA_INBOUND_URL
  // ...
}

function getMessageText(msg) {
  if (!msg || !msg.message) return null;
  return msg.message.conversation ||
    msg.message.extendedTextMessage?.text ||
    msg.message.imageMessage?.caption ||
    null;
}
```

Both `messages.upsert` and `chats.update` handlers use `sendToARA()` for the actual webhook delivery and `getMessageText()` for text extraction. This ensures consistent payload format across both detection paths.

## What Works vs What Doesn't

| Scenario | `messages.upsert` | `chats.update` | Group | Combined |
|----------|------------------|----------------|-------|----------|
| Lead replies to Ava (different number) | ✅ Detected (notify) | N/A (different JID) | N/A | ✅ |
| Owner replies to lead convo (different JID) | ✅ Detected (fromMe) | N/A (different JID) | N/A | ✅ |
| **Owner self-chat reply (pre-LID)** | ❌ Not emitted | ⚠️ Unreliable — `lastMessage` often absent | ✅ Always works | ✅ via Group |
| **Owner self-chat reply (LID format)** | ⚠️ Detected (fromMe) but filtered by self-chat guard — `remoteJid` is `@lid`, guard checks `@s.whatsapp.net` | ❌ Does not fire at all (0/870 log lines) | ✅ Always works | ❌ Broken |
| Bot's own sent message (echo) | Filtered by sentMsgIds | Filtered by sentMsgIds | Filtered by sentMsgIds | ✅ |
| Reconnection history flood | Processed individually | Filtered by timestamp check | Filtered normally | ✅ |

## Debugging Checklist

If an owner reports "I replied on WhatsApp and got nothing":

1. [ ] Check the sidecar log for `"Self-chat detected via chats.update"` — this confirms the `chats.update` handler fired
2. [ ] If no `chats.update` log entry → check Baileys version supports `chats.update` (v6+). Try upgrading `@whiskeysockets/baileys`
3. [ ] Check the sidecar log for `"Owner reply to JID"` — this is the `messages.upsert` handler (should fire for non-self-chat replies)
4. [ ] Check `emitOwnEvents` is `true` in sidecar `index.js` — required for BOTH handlers to see fromMe messages
5. [ ] Check `sentMsgIds` echo filter — the `chats.update` handler also checks this set. If a false-positive collision occurs (extremely rare), the message would be silently dropped
6. [ ] Verify the message appeared on WhatsApp — if the owner replied but it didn't send (phone offline), no chat update will fire
7. [ ] If `chats.update` fired but `sendToARA` failed — check the webhook delivery (Layer 2 in sidecar-debugging.md)
8. [ ] Verify the server's `_handle_owner_coach_whatsapp` received the message (server log)
9. [ ] Check `tenant_id=TENANT_ID` on AgentChatMessage creates (silent failure if missing)

## Architecture Note

Both detection paths (`messages.upsert` and `chats.update`) converge on the same `sendToARA()` helper, which sends a POST to `http://localhost:8766/api/whatsapp/inbound`. The server's `whatsapp_inbound_webhook()` handler then routes based on `owner_reply` flag + `is_owner` check.

```
Sidecar detection paths:
  messages.upsert(notify) ─→ sendToARA() ──→ Server webhook
  messages.upsert(fromMe) ─→ sendToARA() ──→ Server webhook
  chats.update(fromMe)    ─→ sendToARA() ──→ Server webhook
                                     ↑
                              unified payload format:
                              {phone, name, message, owner_reply, message_id, remote_jid}
```

## Related

- This replaces the earlier approach of tracking `messages.set` or `messaging-history.set` — `chats.update` is more reliable because it fires in real-time rather than only on reconnect
- See `references/perisclaw-research.md` for the competitor analysis that led to this approach (OpenClaw, Perisclaw behavior patterns)
- See `references/sidecar-debugging.md` for the full layered debugging methodology including the `chats.update` layer
- The `whatsapp-web-automation` skill (software-development category) also covers Baileys WhatsApp — it has some overlap with this deployment skill
