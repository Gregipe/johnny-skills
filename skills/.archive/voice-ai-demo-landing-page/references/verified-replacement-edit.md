# Verified Replacement Edit Pattern (bulk string edits)

When re-branding a large single-file page, never hand-transcribe it. Apply every change as a list of `(old, new, expected_count)` tuples and only write the file if every assertion passes. This is atomic, exact, and self-verifying.

## Pattern (execute_code)

```python
from pathlib import Path
text = Path(".../index.html").read_text()

# (old, new, expected_count)  — expected_count=None means "report, don't assert"
edits = [
    ("Old Brand Title", "New Brand Title", 1),
    ("#002953", "#4F2170", None),          # global replace, report count
    ("NAVY", "PURPLE", None),
]

failed = []
for old, new, expected in edits:
    n = text.count(old)
    if expected is not None and n != expected:
        failed.append(f"expected {expected}x '{old[:60]}' but found {n}x")
        continue                            # <-- skip, do NOT apply, do not cascade
    if n > 0:
        text = text.replace(old, new)
    elif expected is None:
        failed.append(f"NOT FOUND (global): '{old}'")

if failed:
    print("ABORTED — no file written:")
    for f in failed: print(" -", f)
else:
    Path(".../index.html").write_text(text)
    print("OK — written.")
```

## Pitfalls (both hit in the Mondelez re-brand)

1. **Cascade / ordering bug.** If edit A's target appears inside edit B's target, applying A first makes B report "NOT FOUND". Symptoms: a `count` assert fails with `found 0` on a string you *know* is in the file. Fix: (a) `continue` on any count mismatch so a failed edit never mutates state, and (b) order broad/overlapping replaces **after** targeted ones. Concrete example: `>🏠<` → `>🍫<` was meant for 3 spots (favicon + badge + card icon), but it silently consumed the emoji that two later targeted edits depended on.

2. **Verify against the live file with a read-only probe first.** Before trusting a "NOT FOUND", print `repr()` of the actual line and compare char-by-char — a wrong assumption about the exact string (extra attrs, spacing, `>` vs `> `) costs a full abort cycle.

3. **Prefer exact-count asserts on unique strings** (title, logo URL, copy). Use `expected=None` (report-only) only for global renames like `NAVY`→`PURPLE` where the count is incidental.

4. **Renaming a named color constant does NOT change its literal value.** In the Mondelez re-brand, `NAVY`→`PURPLE` and `ORANGE`→`ACCENT` updated every *reference*, but the accent hex stayed `#FF6700` (Bajaj orange) because the rename only touched the identifier, not `const ACCENT="#FF6700"`. The page served with orange CTAs on a purple sidebar until a final audit caught it. Rule: when you rename a color variable, also change its hex literal, and always close with a **full color audit** — `curl -s localhost:8787/ | grep -oE '#[0-9A-Fa-f]{6}' | sort | uniq -c | sort -rn` — then confirm the only remaining colors are neutrals (gray `#9ca3af`/`#f3f4f6`/`#6b7280`/`#d1d5db`/`#e5e7eb`/`#111827`/`#374151`), semantic status colors (green `#10b981`, blue `#3b82f6`, amber `#f59e0b`/`#d97706`, red `#ef4444`), and the intended new brand colors. Zero old-brand hexes.
