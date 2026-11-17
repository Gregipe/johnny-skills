# WhatsApp Document Ingestion Pipeline (June 2026)

## Architecture

```
WhatsApp: User sends PDF/DOCX/spreadsheet
  ↓
Baileys Sidecar (whatsapp-sidecar/index.js):
  → Detects msg.message.documentMessage
  → downloadContentFromMessage() → chunks → Buffer
  → Base64 encode → POST /api/whatsapp/document-inbound
  ↓
ARA Server (server.py):
  → /api/whatsapp/document-inbound endpoint
  → parse_document(filename, content) extracts text
  → Sends to agent_chat with [DOCUMENT_INGEST: filename]\n\n{text[:8000]}
  ↓
Ava classifies the parsed text:
  → "I see 15 contacts → import as leads?"
  → "This is product info → save as knowledge?"
  → "Sales scripts → I'll learn from these"
  ↓
User confirms → Ava calls import_leads_from_text(text="...")
  → Tool parses the actual document text → creates leads
```

## Sidecar: Document Detection

Added in `whatsapp-sidecar/index.js` — detection block placed BEFORE the
`// Skip non-text messages` gate (line ~538):

```javascript
// ── Document / File message ──
if (msg.message?.documentMessage) {
    if (isAlreadyForwarded(msg.key.id, '[doc]')) continue;
    trackForwarded(msg.key.id);
    trackForwardedContent('[doc]' + ':' + (msg.key.id || ''));
    logger.info(`Document self-chat: ${msg.message.documentMessage.fileName || 'unknown'}, msgId=${msg.key.id}`);
    addPending(ownerPhoneDigits, 'Owner', '[document]', true, msg.key.id, remoteJid);
    const sendResultD = await sendDocumentToARA_promise(msg, ownerPhoneDigits, 'Owner', msg.key.id, remoteJid);
    logger.info(`Document forward result: ${sendResultD}`);
    continue;
}
```

The `sendDocumentToARA_promise()` function follows the same pattern as
`sendAudioToARA_promise()` — downloads bytes, base64-encodes, POSTs to
`/api/whatsapp/document-inbound`.

## ARA Endpoint: /api/whatsapp/document-inbound

Sync endpoint (follows voice-inbound pattern). Receives base64 file,
calls `parse_document()` for text extraction, forwards to agent_chat
with `[DOCUMENT_INGEST:]` marker. Uses `TENANT_ID` constant (single-tenant).

## Tool: import_leads_from_text

Executed when user confirms lead import from document text:

- Parses comma/tab/pipe-separated lines
- Each line: name, phone, email, company
- Creates `Lead` objects with `lead_source="import"`
- Skips lines with no contact info (phone or email)
- Returns summary: "Created N lead(s), skipped M (no contact info)"

**No-hallucination rule:** The LLM NEVER generates lead data. The proposal
is just a question ("import these 15 contacts?"). On confirmation, the
tool reads the ACTUAL document text and creates real DB records.
