# Knowledge Base — Document Ingestion for Sharper Induction

Greg's insight: upload sales decks, process docs, and technical IP BEFORE starting induction. The agent reads them first, then asks sharper questions about gaps between documented strategy and what's actually working.

## Architecture

| Layer | File | Purpose |
|-------|------|---------|
| DB Model | `database.py` → `Document` table | Stores parsed text content per tenant |
| Parse logic | `server.py` → `parse_document()` | Extracts text from PDF/PPTX/DOCX/TXT |
| Upload endpoint | `server.py` → `POST /api/knowledge/upload/{tenant_id}` | Accepts multipart file, parses, persists |
| List endpoint | `server.py` → `GET /api/knowledge/{tenant_id}` | Returns docs list for UI |
| Delete endpoint | `server.py` → `DELETE /api/knowledge/{tenant_id}/{doc_id}` | Removes a document |
| Prompt injection | `server.py` → induction chat endpoint | Injects doc content as `{doc_context}` near skills context |
| UI | `induction_template.py` → Knowledge Base tab | Upload area + drag-drop + doc list |

## Document Parsing

```python
def parse_document(filename, content):
    ext = filename.rsplit(".", 1)[-1].lower()
    text = ""
    if ext == "pdf":
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
    elif ext in ("pptx", "pptm"):
        from pptx import Presentation
        prs = Presentation(io.BytesIO(content))
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    text += shape.text + "\n"
    elif ext in ("docx", "docm"):
        from docx import Document as DocxDocument
        doc = DocxDocument(io.BytesIO(content))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    elif ext == "txt":
        text = content.decode("utf-8", errors="replace")
    return text.strip()
```

## Prompt Injection

Doc content is injected into the LLM system prompt BEFORE the module instructions:

```
## Uploaded Documents (know this before induction):
### filename.pdf
[content summary up to 3000 chars]
```

This means the LLM reads your collateral FIRST, then asks targeted questions about gaps between what's documented and what's actually happening.

## Dependencies

```bash
pip install PyMuPDF python-pptx python-docx python-multipart
```

## Pitfalls

### SQLAlchemy ID is None Until Flush

When adding a new Document (or any model with `default=lambda: str(uuid.uuid4())[:8]`), the `id` field is `None` until SQLAlchemy flushes:

```python
doc_entry = Document(tenant_id=..., filename=...)
db.add(doc_entry)
doc_entry.id  # None!
db.flush()
doc_entry.id  # 'd52efcca' — now usable
```

**Always call `db.flush()` before using the generated ID** in a filepath or response. Without it, `doc_entry.id + "_" + file.filename` crashes with `TypeError: unsupported operand type(s) for +: 'NoneType' and 'str'`.

This is NOT a problem when the ID is passed as a URL path param (FastAPI resolves those from the DB query), but it IS a problem when constructing a local filepath with the ID in the same request handler.

### async Upload Endpoint Needs python-multipart

FastAPI `UploadFile` in async endpoints requires `python-multipart` to be installed:

```bash
pip install python-multipart
```

Without it, the endpoint fails at app startup with: `RuntimeError: Form data requires "python-multipart" to be installed.`

## UI Flow

1. **Knowledge Base tab** (📚) in sidebar — always visible
2. Upload area: dashed border, click-to-browse or drag-and-drop
3. Supported: PDF, PPTX, DOCM, DOCX, TXT — max 10MB
4. After upload: doc appears in list with word count + remove button
5. Docs are injected into the NEXT induction chat message automatically

## File Backup

Raw files stored at `/Users/greg/ara/uploads/{doc_id}_{filename}` for re-processing.
