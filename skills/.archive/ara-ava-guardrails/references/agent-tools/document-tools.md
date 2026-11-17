# New Tools: list_documents & send_attachment

## list_documents

Lists all documents in the knowledge base with type categorization.

**Definition:**
```json
"list_documents": {
  "description": "List all documents in the knowledge base (PDFs, decks, website scrapes). No args.",
  "read_only": true
}
```

**Output format:**
```
📄 Documents in knowledge base:
  📊 Deck | Hunar Conversational AI Agents_Self Serve.pdf (1595 words, 2026-05-21)
  📊 Deck | Voice AI Agents - Hunar White Paper.pdf (1204 words, 2026-05-21)
  🌐 Site | www.hunar.ai (scraped, 2026-06-20)
  📝 Doc  | test_pricing.txt (19 words, 2026-05-30)
```

Categories: `📊 Deck` (source="deck"), `🌐 Site` (source_type="website"), `📝 Doc` (default).

## send_attachment

Sends a document from the knowledge base to a lead via WhatsApp or email.

**Definition:**
```json
"send_attachment": {
  "description": "Send a document from the knowledge base to a lead via WhatsApp. Args: {\"lead_name\": \"...\", \"filename\": \"...\", \"caption\": \"...\"}",
  "read_only": false
}
```

**Args:**
- `lead_name` (required) — resolves via `resolve_lead()`
- `filename` (required) — fuzzy-matched against documents table
- `caption` (optional) — message to send with the document
- `channel` (optional, default "whatsapp") — "whatsapp" or "email"

**WhatsApp path:** Creates temp file from `doc.text_content`, calls `wa.send_document()`, cleans up temp file.

**Email path:** Creates ScheduledAction with `action_type='email'`, attachment filename in payload, fired by email scheduler.

**Fuzzy matching:** Tries exact match first, then `ILIKE %filename%` fallback.

## send_whatsapp_to_owner — Always [ACTION: NOW]

This tool only sends to Greg's phone. It is explicitly marked as `[ACTION: NOW]` in the system prompt:

> *"Tools that send communication TO THE OWNER ALWAYS use [ACTION: NOW]. When the user says 'send me', 'drop me', 'ping me' — execute immediately."*

No confirmation gate for owner-bound tools.
