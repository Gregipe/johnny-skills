# Email Attachment Fallback (June 2026 — Updated)

## Bug: Email Sent Without Attachment (June 24)
The `send_email` tool creates a ScheduledAction with `payload.attachment = "filename.pdf"`. The email scheduler loads from `UPLOAD_DIR/doc_id_filename`. `/opt/ara/uploads/` was EMPTY — documents were stored as `text_content` in the DB, never saved as binary files. Scheduler silently skipped the attachment.

## Fix 1: text_content Fallback (June 24)
When the disk file doesn't exist, create a temp file from `doc.text_content` and attach that.

## Fix 2: PDF Guard (June 25 — CRITICAL)
**PDFs must NEVER fall back to text_content.** The fallback sent Jimmie Tete a 10KB `.txt` file of extracted text instead of a 5MB PDF deck. Embarrassing.

```python
# OLD — dangerous for PDFs:
elif doc.text_content:
    # Sends extracted text as "attachment" — 10KB instead of 5MB

# NEW — only non-PDFs:
elif doc.text_content and not doc.filename.lower().endswith('.pdf'):
    # Safe: .md, .txt, website scrapes get text fallback.
    # PDFs need the original binary — text is not a usable deck.
```

## Root Cause
Upload code at line 1690 DOES save the binary file to disk correctly. But the existing PDFs were uploaded May 21 (before server migration), and the uploads directory didn't survive. The upload code is correct for NEW uploads.

## Long-Term
- New uploads save binary to disk (line 1690, correct)
- Existing docs without binaries need re-upload via Induction page
- PDFs gated from text_content fallback permanently
