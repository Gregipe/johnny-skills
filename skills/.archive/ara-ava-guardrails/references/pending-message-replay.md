# Pending Message Replay — Sidecar Queue

## Mechanism

The WhatsApp sidecar (`/opt/ara/whatsapp-sidecar/index.js`) uses a crash-safe pending queue:

1. **`addPending()`** — Saves message to `pending.json` BEFORE attempting delivery
2. **`sendToARA_promise()`** — POSTs to ARA server at `/api/whatsapp/inbound`
3. On success → `removePendingByMsgId()` removes from queue
4. On failure → message stays in `pending.json`

## Replay

On sidecar startup (line ~404):
```javascript
const pending = loadPending();
for (const p of pending) {
    const ok = await sendToARA_promise(...);
    if (ok) removePendingByMsgId(p.msg_id);
}
```

## Gap: Server Restart Without Sidecar Restart

If the server goes down but the sidecar stays up:
- Sidecar persists messages to `pending.json`
- Messages are NOT replayed until next sidecar restart
- There is no server-startup flush mechanism

## Detection

```bash
cat /opt/ara/whatsapp-sidecar/pending.json
```

Non-empty array = undelivered messages waiting.

## Delivery

```bash
systemctl restart ara-whatsapp-sidecar
```

Triggers replay on startup. Verify with:
```bash
journalctl -u ara-whatsapp-sidecar --since '1 min ago' | grep 'Replaying|Self-chat DM'
```

## Real Example (June 17, 2026)

Greg sent "Hey Ava - create a lead - Amardeep Shekhawat, 1111111117, Pronto" during a server restart window. Message was saved to `pending.json`. Delivered after `systemctl restart ara-whatsapp-sidecar`.

## Sidecar Reconnection Windows

WhatsApp session resets ("Closing open session in favor of incoming prekey bundle") cause ~2-minute reconnection windows during which messages may be lost if they arrive after the old session closes but before the new one initializes. These are NOT saved to pending.json because the sidecar isn't running to receive them.
