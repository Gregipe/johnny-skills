# Email Attachment PDF Fallback Pitfall — June 25, 2026

## Bug: PDF sent as 10KB text file instead of 5MB deck

When Ava sends a PDF from the knowledge base as an email attachment, the email scheduler:
1. Looks for the file at `UPLOAD_DIR/<doc_id>_<filename>.pdf`
2. If not found → falls back to `doc.text_content` → creates a temp `.txt` file
3. Emails the text extract as the "attachment"

**Result:** Jimmie received a 10KB text file (`Hunar Conversational AI Agents_Self Serve.pdf` containing extracted text) instead of the actual 5MB deck.

## Root Cause

The uploads directory was empty. PDFs uploaded in May 2026 had their text extracted and stored in the DB, but the original binary was lost during a server migration. The email scheduler's fallback to `text_content` was meant for `.md`/`.txt` files where text IS the file — but it was applied blindly to PDFs too.

## Fix (server.py, email scheduler)

**Before:**
```python
elif doc.text_content:
    # Fall back to text_content for any file
    tmp.write(doc.text_content[:100000])
    attachments = [(doc.filename, f.read())]
```

**After:**
```python
elif doc.text_content and not doc.filename.lower().endswith('.pdf'):
    # Only fall back to text for non-PDF formats
    # PDFs need the original binary — text extract is not a usable deck
    tmp.write(doc.text_content[:100000])
    attachments = [(doc.filename, f.read())]
```

**Result:** PDFs without a binary file now skip the attachment with a warning log. Better to send nothing than to send extracted text masquerading as a deck.

## Prevention

- New PDF uploads save the binary correctly (line 1690 in server.py: `f.write(content)`)
- The upload code always saved the file — the issue was migration-related data loss
- Existing PDFs without binaries must be RE-UPLOADED through the Induction page

## Re-upload flow

1. Delete old document entry from knowledge base
2. Go to Induction → upload the PDF again
3. New entry will have binary saved to `UPLOAD_DIR/`
4. Email attachments will now include the full 5MB PDF

## Detection query

```sql
SELECT filename, LENGTH(text_content) as text_size
FROM documents
WHERE filename LIKE '%.pdf'
AND LENGTH(text_content) < 50000;  -- Suspect: PDF should be MBs
```
