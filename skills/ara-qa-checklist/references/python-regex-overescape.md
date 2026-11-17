# Python Regex Backslash Over-Escape in Raw Strings

## The Pitfall

In Python, `r"\["` produces the string `\[` — one backslash followed by `[`.
When passed to `re.compile()`, `\[` means "escaped bracket" = literal `[`.

**Writing `r"\\["`** produces the string `\\[` — TWO backslashes followed by `[`.
When passed to `re.compile()`, `\\` means "literal backslash" (escaped backslash), then `[` means "start of character class".
**This does NOT match `[`.**

## The Bug

```python
# BAD — quadruple over-escape in raw string
r"\\\\[SUGGEST_DEAL: org=([^,]+), domain=([^,]+), lead=([^,]+), lead_id=([^\\\\]]+)\\\\\\]"

# In raw string: \\\\[ = 4 backslash chars + [
# re.compile sees: \\\\[ = two escaped backslashes (\\) + start of char class
# Matches: \\S... (two literal backslashes + SUGGEST_DEAL) — NEVER matches [S...
```

## The Fix

```python
# CORRECT — single backslash before bracket
r"\[SUGGEST_DEAL: org=([^,]+), domain=([^,]+), lead=([^,]+), lead_id=([^\]]+)\]"

# In raw string: \[ = 1 backslash + [
# re.compile sees: \[ = escaped bracket = literal [
# Matches: [SUGGEST_DEAL:...] — what the output actually contains
```

## How This Happens

Someone with Java/C# regex background (where `\\` is needed to get one regex backslash) codes in Python and writes `\\` out of habit. When that doesn't compile, they add MORE backslashes instead of removing them. Wrong direction.

In Python **raw strings**, backslashes are literal:
- `r"\["` → string contains `\[` → regex sees `\[` = literal `[` ✅
- `r"\\["` → string contains `\\[` → regex sees `\\` = literal `\`, `[` = char class ❌

**Rule of thumb:** In a raw string, you need EXACTLY ONE `\` before a bracket to escape it for regex. Not zero, not two, not four.

## Test It

```python
import re

# Single backslash — correct
pat1 = re.compile(r"\[SUGGEST_DEAL: org=([^\]]+)\]")
print(pat1.search("[SUGGEST_DEAL: org=Test]"))  # ✅ Match

# Double backslash — broken
pat2 = re.compile(r"\\[SUGGEST_DEAL: org=([^\]]+)\\]")  # ❌ Compile error or wrong match
```
