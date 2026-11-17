# Chunked Document Skill Extraction

## The Bug
`extract_skills_from_document()` used `doc.text_content[:6000]` — only the first 6,000 characters of any document were skill-extracted. A 50-page PDF had pages 3-50 as dead storage: stored in the DB but invisible to search and induction.

## The Fix
Replace single-slice extraction with per-chunk extraction:

```python
chunk_size = 6000
chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
for i, chunk_text in enumerate(chunks):
    chunk_label = f"{doc.filename} (part {i+1}/{len(chunks)})"
    # extract skills from each chunk
```

Each chunk gets its own LLM call. Skills are deduplicated by key (first occurrence wins). Chunks are labeled so the user can trace which part of the document produced which skills.

## Why 6000?
The limit was arbitrary — not a model constraint. DeepSeek V4 Flash has a 128K context window. 6000 chars ≈ 1500 tokens ≈ $0.00018. The fix doesn't increase per-chunk cost; it just calls the LLM N times instead of 1.

## Pitfalls
- **Cost**: A 50K-char document with 9 chunks costs ~$0.0016 (9 × $0.00018). Negligible.
- **Duplicate keys**: Skills with the same key from different chunks are deduplicated (first wins). This means if a PDF repeats information, only the first occurrence is captured. Consider merging values instead for future enhancement.
- **Non-document extraction**: This fix only applies to `extract_skills_from_document()`. The induction coach's `===SAVE_SKILL===` path is unaffected.
