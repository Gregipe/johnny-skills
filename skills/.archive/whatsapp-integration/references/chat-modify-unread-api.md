# Chat Modify API — Mark Chat as Unread

## Discovery (June 23, 2026)

During Build 3 (WhatsApp unread marking), the initial implementation proposed:
```javascript
await sock.chatModify({ markChat: 'unread' }, jid);
```

**This API does NOT exist.** Inspecting Baileys source at `node_modules/@whiskeysockets/baileys/lib/Utils/chat-utils.js` reveals `chatModificationToAppPatch()` checks for `'markRead' in mod` — there is NO `markChat` branch.

## Correct API

```javascript
await sock.chatModify({ markRead: false, lastMessages: [lastMsg] }, jid);
```

Where `lastMsg` is:
```javascript
{ key: result.key, messageTimestamp: result.messageTimestamp || Math.floor(Date.now() / 1000) }
```

**Setting `markRead: false` with `lastMessages` tells WhatsApp "this chat has unread messages up to this point"** — effectively marking it as unread.

## Requirements

1. `lastMessages` is **required** — Baileys source comment: "requires the last messages till the last message received; required for archive & unread"
2. The `lastMsg` must contain the Baileys message key from the last sent message
3. Without valid `lastMessages`, WhatsApp server silently ignores the sync action

## Persistence Across Restarts

The `lastSentMessages` Map (phone → last message key) is in-process state. It is lost on sidecar restart. To survive restarts:

```javascript
const lastSentMessages = new Map();
const LAST_SENT_FILE = path.join(__dirname, "last_sent.json");

function loadLastSent() {
  try {
    if (!fs.existsSync(LAST_SENT_FILE)) return;
    const data = JSON.parse(fs.readFileSync(LAST_SENT_FILE, "utf8"));
    for (const [phone, msg] of Object.entries(data)) {
      lastSentMessages.set(phone, msg);
    }
  } catch (e) { logger.warn("Failed to load last-sent state: " + e.message); }
}

function saveLastSent() {
  try {
    const obj = {};
    for (const [phone, msg] of lastSentMessages) {
      obj[phone] = msg;
    }
    fs.writeFileSync(LAST_SENT_FILE, JSON.stringify(obj));
  } catch (e) { logger.warn("Failed to save last-sent state: " + e.message); }
}

loadLastSent(); // call at startup
```

**Error handling**: Return `{ ok: false, error: 'no last message tracked' }` when the map is empty — do NOT silently return `ok: true`.

## Multi-Device Sync Conflict

When Baileys (linked device) marks a chat as unread but WhatsApp Web (another linked device) is open, WA Web may immediately fire its own `markChatAsRead` sync. This is an inherent multi-device limitation.

**Mitigation**: Call `mark_unread_sync()` only when the sidecar is the most recently active linked device. Accept as "best-effort" — works reliably when WA Web is backgrounded, unreliable when foregrounded (but the user is watching the chat in that case, so unread badge is irrelevant).

## Sidecar Endpoint

```javascript
app.post('/mark-unread', async (req, res) => {
  const { phone } = req.body;
  if (!phone) return res.status(400).json({ ok: false, error: 'phone required' });
  if (!sock || connectionState !== 'connected') {
    return res.json({ ok: false, error: `WhatsApp not connected (${connectionState})` });
  }
  const cleaned = phone.replace(/[^0-9]/g, '');
  const jid = `${cleaned}@s.whatsapp.net`;
  const lastMsg = lastSentMessages.get(phone);
  if (!lastMsg?.key) {
    return res.json({ ok: false, error: 'no last message tracked' });
  }
  try {
    await sock.chatModify({ markRead: false, lastMessages: [lastMsg] }, jid);
    res.json({ ok: true });
  } catch (e) {
    res.json({ ok: false, error: e.message });
  }
});
```

## Python Client

```python
def mark_unread_sync(self, phone):
    """Mark a WhatsApp chat as unread for notification visibility."""
    result = _req("POST", "/mark-unread", {"phone": phone}, timeout=5)
    return result.get("ok", False)
```

Uses `_req()` helper (NOT `requests`) — the Python client uses `urllib`.
