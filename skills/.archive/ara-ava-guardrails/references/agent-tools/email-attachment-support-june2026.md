# Email Attachment Support — June 2026

## Problem
Emails sent via `send_email` tool arrived without attachments even when `attachment` parameter was specified. Two separate gaps:

1. **send_email tool handler** (line 4325): Added attachment lookup from Documents table, fuzzy match on filename, stored in ScheduledAction payload
2. **Email dispatch** (line 8063): Was calling `send_via_gmail_api(tokens, email, subject, body)` WITHOUT the attachments parameter

## Fix

### Tool handler side (server.py ~line 4325)
```python
attachment = args.get("attachment", "")
if attachment:
    doc = db.query(Document).filter(
        Document.tenant_id == tenant_id,
        Document.filename.ilike(f"%{attachment}%"),
    ).first()
    if doc:
        attachment_path = doc.filename
```

Stores `attachment` in ScheduledAction payload dict.

### Dispatch side (server.py ~line 8063)
```python
elif action.action_type == "email":
    attachment_filename = payload.get("attachment", "")
    attachments = None
    if attachment_filename:
        # Find document in DB
        doc = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.filename == attachment_filename,
        ).first()
        if doc:
            filepath = os.path.join(UPLOAD_DIR, f"{doc.id}_{doc.filename}")
            if os.path.exists(filepath):
                with open(filepath, "rb") as f:
                    attachments = [(attachment_filename, f.read())]
    success, err_msg = send_via_gmail_api(tokens, lead.email, subject, body, attachments=attachments)
```

## Requirements
- Files must be uploaded via dashboard (not chat) — dashboard uploads save to `UPLOAD_DIR/{doc_id}_{filename}`
- Chat `upload_document` tool stores text only in DB, no file on disk
- `send_via_gmail_api` already supports `attachments: list[tuple[str, bytes]]`

## Pitfall
The uploads directory was empty (0 files) on June 16 despite documents existing in DB. This caused all attachment attempts to silently fail. Files must be re-uploaded via dashboard.
