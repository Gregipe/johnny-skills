---
name: encrypted-pdf-analysis
description: "Use when a PDF is encrypted or password-protected."
version: 1.0.0
author: Johnny (curator)
license: MIT
metadata:
  hermes:
    tags: [pdf, encryption, documents, lic, insurance, finance]
    category: productivity
---

# Encrypted PDF Analysis

Unlock and analyze password-protected PDFs — bank statements, insurance policies, tax documents (the default packaging for Indian personal documents) — without leaving plaintext copies behind.

## When to use

- `read_file` on a PDF fails with `EncryptedError: document is encrypted`.
- The user hands over a password-protected document and asks what it entails.

## Procedure

1. **Detect.** A `read_file` EncryptedError means a real encryption layer (Hermes's built-in extractor already tried and failed). Check for local PDF tooling first (`qpdf`, `pdftotext`, python `pypdf`/`pikepdf`); this Mac has none by default, so the bootstrap below is the reliable path.
2. **Bootstrap tools in scratch, never system pip.**
   `mkdir -p "$TMPDIR/pdfwork" && cd "$TMPDIR/pdfwork" && uv venv .venv && uv pip install --python .venv/bin/python pypdf pikepdf`
   TMPDIR is the profile scratch dir and auto-prunes idle files, so extraction artifacts expire on their own.
3. **Password ladder — stop at first success, never go past the candidate rung:**
   a. Empty password: `pikepdf.open(path, password="")` — many "encrypted" PDFs are owner-password-only and open with nothing.
   b. Obvious derived candidates only: tokens from the filename (reference/policy numbers), short DOB fragments, the owner's name. A handful, not a wordlist.
   c. Ask the user via `clarify` with concrete options: type the password / save a password-free copy themselves / ask the sender. The user is fine typing a password in chat for their own document — never store it, never echo it, and one line reminding them the chat copy is theirs to manage.
4. **Decrypt + extract.** Verify with `pikepdf.open(password=...)`; then pypdf: `PdfReader(path).decrypt(pw)` (nonzero return = success), loop `page.extract_text()` across all pages, join into a scratch `fulltext.txt`, and read it in chunks with `read_file`. Never write a decrypted PDF copy to disk.
5. **Schedule/table pages extract jumbled.** LIC-style schedules put field labels and values in separate text layers: run BOTH plain `extract_text()` (yields the values) and `extract_text(extraction_mode="layout")` (yields the labels), then map values to fields by position. Annexure tables that return empty are images — report that they didn't extract; never invent the numbers.
6. **Summarize flag-first.** Lead with what the document is, then the actionable facts: due dates vs today, grace windows, expiries, and thresholds the holder has crossed (loan/surrender eligibility). See `references/lic-policy-documents.md` for the LIC field map and flag checklist.
7. **Cleanup.** Confirm no decrypted PDF exists on disk; the scratch text file auto-prunes. Offer to delete the scratch dir or produce a password-free copy in the user's Downloads only if they ask.

## Pitfalls

- pypdf `decrypt("")` returning 0 / `FileNotDecryptedError` only means the empty password failed — cross-check with pikepdf (`PasswordError`) before moving up the ladder.
- Don't brute-force beyond the derived-candidate rung. The password may be the sender's choice, not the user's; one `clarify` round-trip is cheaper and correct.
- Keep the password out of memory and out of any file you write. Extraction text dumps contain the document contents — keep them in scratch, not Downloads/Desktop.
- A blocked cleanup `rm` (approval timeout with the user away) must not be retried: state where the artifacts live and that scratch auto-prunes, then move on.
- The bundled `pdf` skill covers decrypt-with-a-KNOWN password (`pdf_secure.py --decrypt`); this skill is for the unknown-password path plus document analysis.

## References

- `references/lic-policy-documents.md` — LIC policy document anatomy, schedule field map, and the flag checklist for summarizing Indian life-insurance policies.
