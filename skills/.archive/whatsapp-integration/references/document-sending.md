# WhatsApp Document/Attachment Sending (June 2026)

## Sidecar Endpoint: `/send-document`

```javascript
async function sendDocument(phone, filePath, fileName, caption) {
  if (!sock || connectionState !== 'connected') {
    return { ok: false, error: `WhatsApp not connected (${connectionState})` };
  }
  try {
    const cleaned = phone.replace(/[^0-9]/g, '');
    const jid = `${cleaned}@s.whatsapp.net`;
    const docBuffer = fs.readFileSync(filePath);
    const result = await sock.sendMessage(jid, {
      document: docBuffer,
      fileName: fileName || path.basename(filePath),
      mimetype: 'application/pdf',
      caption: caption || ''
    });
    return { ok: true, msgId: result?.key?.id || 'unknown' };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

app.post('/send-document', async (req, res) => {
  const { phone, filePath, fileName, caption } = req.body;
  if (!phone || !filePath) return res.status(400).json({ ok: false, error: 'phone and filePath required' });
  const result = await sendDocument(phone, filePath, fileName, caption);
  res.json(result);
});
```

## Python Client: `send_document()`

```python
def send_document(self, phone, file_path, file_name=None, caption=None):
    """Send a document/PDF via WhatsApp. Returns {status, msg_id}."""
    payload = {"phone": phone, "filePath": file_path}
    if file_name:
        payload["fileName"] = file_name
    if caption:
        payload["caption"] = caption
    return _req("POST", "/send-document", payload)
```

### CRITICAL PITFALL: `self._req` vs `_req` (June 2026)

`_req` is a module-level function in `whatsapp_sidecar_client.py`, NOT a method on the `BaileysWA` class. Calling `self._req(...)` raises `AttributeError: 'BaileysWA' object has no attribute '_req'`.

**Fix:** Always call `_req(...)` directly, never `self._req(...)`.

All other methods in the client (`send_message_sync`, `send_to_jid`, `mark_unread_sync`) use the module-level `_req()`. New methods must follow the same pattern.

## Email Attachment Fallback (June 2026)

When sending email with an attachment, the email scheduler looks for the file at `{UPLOAD_DIR}/{doc_id}_{filename}`. Legacy documents uploaded before the current server may only have `text_content` in the database with no file on disk. Without a fallback, the email is sent WITHOUT the attachment.

**Fix in `_execute_action` email path:** When the file doesn't exist on disk, create a temporary file from `doc.text_content` and attach that:

```python
if doc:
    filepath = os.path.join(UPLOAD_DIR, doc.id + "_" + doc.filename)
    if os.path.exists(filepath):
        with open(filepath, "rb") as f:
            attachments = [(doc.filename, f.read())]
    elif doc.text_content:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, prefix='ara_attach_')
        tmp.write(doc.text_content[:100000])
        tmp.close()
        with open(tmp.name, 'rb') as f:
            attachments = [(doc.filename, f.read())]
        os.unlink(tmp.name)
```

## `send_attachment` Tool for Ava

Server-side tool that sends a document from the knowledge base to a lead via WhatsApp or email:

- `lead_name` + `filename` → resolves lead, finds document by fuzzy filename match
- `channel: "whatsapp"` → creates temp file from `text_content`, calls `wa.send_document()`
- `channel: "email"` → creates ScheduledAction with attachment filename, scheduler handles send
