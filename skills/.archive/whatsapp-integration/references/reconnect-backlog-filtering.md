# Reconnect Backlog Filtering (Self-Chat)

## Problem

When the Baileys WebSocket reconnects after a disconnect (including the ~50-minute server-side timeout), WhatsApp replays pending offline messages via `messages.upsert`. For self-chat (owner messaging themselves), this includes messages Greg sent during the disconnect window — which may have already been responded to, or are outdated context.

Before this fix, every reconnected message was forwarded to ARA as a new user message, triggering Ava to re-respond to old content. This caused:

- Ava replying to "wow - finally!" messages from 40 minutes ago
- Confusing double-responses in the coaching group
- Greg receiving stale or duplicative responses

## Solution

### BOTH Detection Paths Need the Filter

The sidecar has **two** independent detection paths for self-chat messages. Both fire on reconnect and both need the same backlog filter:

**Path 1: `messages.upsert`** (catches real-time messages + reconnect replay)
```javascript
if (isSelfChat) {
  const msgTime = (msg.messageTimestamp || 0) * 1000;
  const age = Date.now() - msgTime;
  if (age > 15000) {
    logger.info(`Self-chat DM skipped (backlog): "${text.substring(0, 60)}..." (age=${Math.round(age/1000)}s)`);
    continue;
  }
}
```

**Path 2: `chats.update`** (catches messages that `messages.upsert` misses -- fires independently on reconnect)
```javascript
if (isSelfChat2) {
  const msgTime = (lastMsg?.messageTimestamp || 0) * 1000;
  const age = Date.now() - msgTime;
  if (age > 15000) {
    logger.info(`Chats.update self-chat skipped (backlog): age=${Math.round(age/1000)}s`);
    continue;
  }
}
```

**CRITICAL: Both paths must be updated together.** Fixing only `messages.upsert` while leaving `chats.update` unfixed means stale reconnect messages continue to leak through the second path -- which is exactly what happened in the June 2026 incident. The `chats.update` handler is easy to miss because its comment says "self-chat" but the original code had NO timestamp check.

## Why 15 Seconds?

- **Too short (1-5s)**: Legitimate messages sent during a brief network blip would be lost
- **Too long (60s+)**: Backlog from a 50-second reconnect could still sneak through
- **15 seconds**: Accounts for Baileys processing delay + network latency + the brief window between message creation and sidecar processing

The 15s threshold is a heuristic. If legitimate messages are being filtered out, increase it. If backlog still leaks through, decrease it.

## Why Only Self-Chat?

Only self-chat messages get the backlog filter. Lead messages (inbound from prospects) are always forwarded because:
- Every lead message represents a real business opportunity
- Lead conversations don't create "stale responses" the way self-chat coaching does
- Backlog from leads during a reconnect is expected — they messaged while we were offline and need a response

## Logging

Filtered backlog messages are logged so you can verify the filter is working:

```
[15:12:46] Self-chat DM skipped (backlog): "wow - finally!..." (age=53s)
```

Check `/tmp/sidecar.log` after a reconnect to confirm.
