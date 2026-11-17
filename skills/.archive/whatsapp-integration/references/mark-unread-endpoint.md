# Mark-Unread Endpoint — Full Implementation

Added June 23, 2026 to solve WhatsApp Web "read" status issue. When Ava sends a message via Baileys sidecar, WhatsApp Web auto-marks it as read. Marking the chat as unread after sending creates a green notification badge.

## Sidecar Changes (whatsapp-sidecar/index.js)

### State tracking + persistence
```javascript
// Near other state maps (~line 114)
const lastSentMessages = new Map(); // phone -> { key, messageTimestamp }
const LAST_SENT_FILE = path.join(__dirname, "last_sent.json");

function loadLastSent() {
  try {
    if (!fs.existsSync(LAST_SENT_FILE)) return;
    const data = JSON.parse(fs.readFileSync(LAST_SENT_FILE, "utf8"));
    for (const [phone, msg] of Object.entries(data)) {
      lastSentMessages.set(phone, msg);
    }
    logger.info("Loaded last-sent state: " + Object.keys(data).length + " entries");
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

loadLastSent();
```

### Track last sent in sendMessage()
```javascript
// After successful send (~line 884):
if (result?.key) {
  lastSentMessages.set(phone, { key: result.key, messageTimestamp: result.messageTimestamp || Math.floor(Date.now() / 1000) });
  saveLastSent();
}
```

### Endpoint (before "// ── Start ──" section)
```javascript
// ── Mark chat as unread (for notification visibility on WhatsApp Web) ──
app.post('/mark-unread', async (req, res) => {
  const { phone } = req.body;
  if (!phone) {
    return res.status(400).json({ ok: false, error: 'phone required' });
  }
  if (!sock || connectionState !== 'connected') {
    return res.json({ ok: false, error: `WhatsApp not connected (${connectionState})` });
  }
  const cleaned = phone.replace(/[^0-9]/g, '');
  const jid = `${cleaned}@s.whatsapp.net`;
  const lastMsg = lastSentMessages.get(phone);
  
  if (!lastMsg?.key) {
    logger.warn(`Cannot mark unread for ${phone}: no last message tracked`);
    return res.json({ ok: false, error: 'no last message tracked' });
  }
  
  try {
    await sock.chatModify({ markRead: false, lastMessages: [lastMsg] }, jid);
    logger.info(`Marked chat unread: ${jid}`);
    res.json({ ok: true });
  } catch (e) {
    logger.warn(`Failed to mark unread for ${phone}: ${e.message}`);
    res.json({ ok: false, error: e.message });
  }
});
```

## Python Client Changes (whatsapp_sidecar_client.py)

```python
def mark_unread_sync(self, phone):
    """Mark a WhatsApp chat as unread for notification visibility."""
    result = _req("POST", "/mark-unread", {"phone": phone}, timeout=5)
    if result.get("ok"):
        return True
    return False
```

## Server Integration (server.py)

Called after `wa.send_message_sync(admin.phone, ...)` in:
1. `_execute_action()` — whatsapp_to_owner handler (after sending reminder)
2. `_handle_owner_coach_whatsapp()` — after sending coaching reply

```python
wa.mark_unread_sync(admin.phone)  # Mark unread for notification visibility
```

## Pitfalls

1. **`markRead: false`, NOT `markChat: 'unread'`** — The Baileys `chatModificationToAppPatch()` function checks for `'markRead' in mod`. There is NO `markChat` branch. Using `markChat` silently fails.
2. **`lastMessages` is required** — Baileys source: "requires the last messages till the last message received; required for archive & unread." Without it, WA server rejects silently.
3. **Silent `ok: true` on empty Map** — After sidecar restart, `lastSentMessages` is empty. Must return `ok: false` with explicit error, not `ok: true` which hides the no-op from all callers.
4. **Multi-device re-mark** — WA Web (another linked device) may immediately re-mark the chat as read. Best-effort feature.
5. **Connection guard required** — `sock` is null during reconnect. Must check `connectionState === 'connected'` before calling `chatModify`.
