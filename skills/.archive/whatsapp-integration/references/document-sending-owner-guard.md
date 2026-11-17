# WhatsApp Sidecar — Document Sending & Owner Guard

## Document Sending

The sidecar supports sending documents/PDFs via WhatsApp using Baileys `sendMessage` with the `document` type.

### Sidecar Endpoint
```
POST /send-document
Body: { "phone": "919582549236", "filePath": "/path/to/file.pdf", "fileName": "deck.pdf", "caption": "Here you go" }
Response: { "ok": true, "msgId": "..." }
```

### Python Client
```python
wa.send_document(phone, file_path, file_name=None, caption=None)
```
Returns `{ "status": "sent", "msg_id": "..." }` or `{ "status": "failed", "error": "..." }`.

Uses module-level `_req("POST", "/send-document", payload)` — NOT `self._req()`.

### MIME Types Supported
.pdf, .doc, .docx, .pptx, .xls, .xlsx, .png, .jpg, .jpeg, .txt, .csv

## Owner Guard

All admin-bound WhatsApp operations are locked to Greg's phone number (919582549236):

```python
wa.send_to_owner(text)        # Always sends to 919582549236
wa.mark_unread_owner()        # Always marks 919582549236 as unread
```

These look up the admin phone from the users table at init time (`_owner_phone`). Server.py uses ONLY these methods for admin notifications — never `send_message_sync(admin.phone, ...)`.

### NEVER send WhatsApp to any number except the admin phone. Use send_to_owner() exclusively.

## Systemd Auto-Restart

The sidecar runs as a systemd service with auto-restart:

```
[Service]
Restart=always
RestartSec=10
```

If WhatsApp disconnects (normal Baileys behavior), the sidecar will reconnect. If it crashes, systemd restarts it within 10 seconds.

## Pitfalls

### loadLastSent() must come AFTER logger init
The `loadLastSent()` function uses `logger`. If called before `logger` is initialized (line ~472), the sidecar crashes on startup with `ReferenceError: Cannot access 'logger' before initialization`. Call `loadLastSent()` only after the `const logger = P({...})` line.

### QR Re-scan on rapid restart
If the sidecar is restarted too quickly (multiple times within seconds), the Baileys auth state can be corrupted. The sidecar will enter a "not logged in, attempting registration" loop. Fix: scan new QR code from `GET /qr`.

### _req is module-level, not method
The `_req()` function is defined at module level (line 16 of whatsapp_sidecar_client.py). All instance methods call `_req(...)`, not `self._req(...)`. Using `self._req()` causes `AttributeError`.

### BaileysWA.__init__ attributes
When patching `__init__`, preserve ALL existing attributes: `page`, `context`, `on_inbound_message`, `on_outbound_message`, `_last_status`, `_last_status_time`, `_status_cache_ttl`. Verify with `test_baileys_init.py`.
