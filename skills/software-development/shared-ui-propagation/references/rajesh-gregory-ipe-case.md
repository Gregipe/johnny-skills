# Case Study: Rajesh → Gregory Ipe Propagation Failure

## What Happened

Changed the lead preview from "Rajesh Sharma / Acme Manufacturing" to "Gregory Ipe / Swiggy" in `cadence_template.py`. Only patched 1 of 6 occurrences.

## Root Cause

Text "→ Rajesh Sharma, Acme Mfg" appeared in **6 independent code paths** within the same file:

| # | Location | Type |
|---|----------|------|
| 1 | Initial HTML render — `previewLead` span | Template literal in Python string |
| 2 | `generatePreview()` — loading state | JS function call site |
| 3 | `staticFallback()` — default variables | JS fallback function |
| 4 | Template switch handler — resets on template change | JS event handler |
| 5 | Step picker — shows on add step | JS event handler |
| 6 | Drag-drop reorder — shows on reorder | JS event handler |

## The Mistake

Used `patch` with context from `read_file(offset=X, limit=Y)` — only saw 1 occurrence. Assumed it was the only one.

## The Fix

After every string substitution:

```bash
grep -c 'old-value' filename   # count occurrences
grep -c 'new-value' filename   # verify how many got changed
# If old count > 0, you missed some
```

In this case, there were 5 remaining "Rajesh" references after the first patch. Needed grep to find them all.

## Lesson Hardened

All string substitutions must end with `grep -c 'old-value'` on the file. Zero matches = done. One or more = more work needed.
