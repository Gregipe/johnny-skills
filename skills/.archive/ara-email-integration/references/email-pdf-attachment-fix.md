# Email PDF Attachment Fix — June 25, 2026

## The Bug

When `send_email` tool was called with `attachment="Hunar Conversational AI Agents_Self Serve.pdf"`, the email went to Jimmie Tete with a 10KB text file instead of the 5MB PDF deck.

## Root Cause

The original PDF binary was never saved to disk (uploads directory empty — files from May 21 migration). The email scheduler's fallback code:
```python
elif doc.text_content:
    # Create temp file from extracted text
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', ...)
    tmp.write(doc.text_content[:100000])
```

This created a `.txt` file from extracted text and attached it. For PDFs/decks, the extracted text is a useless substitute — 10KB of plain text instead of the actual formatted deck.

## Fix (June 25, 2026)

Block the text_content fallback for PDF files:
```python
elif doc.text_content and not doc.filename.lower().endswith('.pdf'):
    # Only fall back to text for non-PDF formats (.md, .txt, kb scrapes)
```

If the original PDF binary is missing, the attachment is skipped with a warning:
```
logger.warning(f"PDF original not found, skipping attachment: {filepath}")
```

## Re-upload Required

Existing PDFs from the May 21 migration have no binary on disk. Re-upload through the Induction page to store the original file. New uploads save the binary correctly at `UPLOAD_DIR/{id}_{filename}`.

## Code Location

`server.py` ~line 9381 — `_execute_action` for email type, attachment loading section.
