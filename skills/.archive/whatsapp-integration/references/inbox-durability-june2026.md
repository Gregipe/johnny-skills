# Inbox-First Message Durability (June 2026)

Replaces `pending.json` file-based persistence with a SQLite `inbox_messages` table in `ara.db`.

## Problem

Messages arriving during the ~2-minute sidecar reconnection window were silently lost. `pending.json` only replayed messages the sidecar had already accepted; messages arriving mid-reconnect were never persisted anywhere, so they vanished.

**Specific incident:** Jun 17, 04:44 UTC — "Yes" confirming a Spectrum deal. Sidecar restarted due to WhatsApp session reset. "Yes" never reached the server or DB.

## Fix: Inbox-First Pattern

**Invariant:** A message is durably stored before any filtering, routing, or self-chat logic runs. A crash or reconnect after the write loses nothing.

### SQLite Table

```sql
CREATE TABLE IF NOT EXISTS inbox_messages (
    id VARCHAR PRIMARY KEY,
    sender TEXT,
    timestamp TEXT,
    body TEXT,
    processed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
```

### Functions in `whatsapp-sidecar/index.js`

```javascript
// Write BEFORE any filtering — durable storage at point of receipt
function inboxWrite(msgId, sender, timestamp, body)

// Mark after successful 200 from ARA
function inboxMarkProcessed(msgId)

// Check if already processed (replaces backlog age check + dedup)
function inboxIsProcessed(msgId)

// Load unprocessed for crash-recovery replay
function inboxLoadUnprocessed()
```

### Message Processing Order

Each message entry point follows this order:

1. `inboxWrite()` — durable write BEFORE any filtering
2. `inboxIsProcessed()` — skip if already processed in a prior session
3. Backlog check (age > 5 min, not in inbox → skip stale messages)
4. Dedup (sentMsgIds, forwardedMsgIds)
5. `sendToARA_promise()` — forward to server
6. `inboxMarkProcessed()` — only after 200 response

### Crash Recovery

On startup, replaces `loadPending()` with `inboxLoadUnprocessed()`:
```javascript
const unprocessed = inboxLoadUnprocessed();
for (const row of unprocessed) {
    const ok = await sendToARA_promise(/* parse row.body */);
    if (ok) inboxMarkProcessed(row.id);
}
```

### Call Sites Patched

All 5 message entry points patched:
- Text self-chat via `messages.upsert`
- Voice notes via `messages.upsert`
- Documents via `messages.upsert`
- Self-chat via `chats.update`
- Direct text messages

### Deleted

- All `addPending()` call sites (function definition remains as dead code)
- All `removePendingByMsgId()` call sites
- `pending.json` file — no longer used for persistence

### Key Difference from pending.json

| | pending.json | inbox_messages |
|---|---|---|
| Write timing | Before forwarding, after filtering | FIRST action, before ALL filtering |
| Backlog coverage | Only messages already accepted | ALL messages that arrive get written |
| Crash recovery | File-based, loses state on rm | SQLite in ara.db, survives everything |
| Dedup | None | inboxIsProcessed() for cross-session dedup |
