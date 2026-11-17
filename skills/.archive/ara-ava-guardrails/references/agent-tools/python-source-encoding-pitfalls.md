# Python Source Encoding Pitfalls

## Problem 1: Smart Quotes in String Literals

**Symptom:** `SyntaxError: unterminated string literal` or `SyntaxError: invalid character '—' (U+2014)` at a line that looks normal.

**Root cause:** The source file contains non-ASCII Unicode characters that look like ASCII punctuation but aren't:
- Right single quotation mark `'` (U+2019) — looks like `'` but isn't
- Left/right double quotes `"`/`"` (U+201C/U+201D)
- Em dash `—` (U+2014) — should be `--` or `—`
- En dash `–` (U+2013)

These are invisible to the human eye when skimming code but cause Python 3.14's stricter parser to reject the file.

**Fix:**
```python
with open("server.py", "rb") as f:
    content = f.read()

replacements = {
    b'\xe2\x80\x98': b"'",   # left single quote
    b'\xe2\x80\x99': b"'",   # right single quote
    b'\xe2\x80\x9c': b'"',   # left double quote
    b'\xe2\x80\x9d': b'"',   # right double quote
    b'\xe2\x80\x93': b'-',   # en dash
    b'\xe2\x80\x94': b'--',  # em dash
}
for old, new in replacements.items():
    content = content.replace(old, new)

with open("server.py", "wb") as f:
    f.write(content)
```

**Prevention:** When copying text from web pages, documents, or chat apps, paste into a plain-text editor first to strip smart quotes. Always run `py_compile.compile()` before committing.

## Problem 2: Doubled Triple-Quotes from String Replacement

**Symptom:** `SyntaxError: invalid syntax` or `SyntaxError: unterminated triple-quoted string literal` near a `"""` boundary.

**Root cause:** When using `.replace(old_block, new_block)` to swap a large multiline string (like a system prompt), if `old_block` is sliced with `content[start:end]` where `end` points to the **start** of the closing `"""` marker, the old closing `"""` stays in the file. The new block also has a closing `"""`. The result is `""""""` (6 quotes).

Example:
```python
# BAD — old_end excludes the closing """
old_end = content.find('"""\n\n# ── Next section', old_start)
old_block = content[old_start:old_end]  # Does NOT include closing """
content = content.replace(old_block, NEW_PROMPT, 1)
# Result: ...content...""" (new prompt close) """ (old close) ...
```

**Fix options:**

1. **Use slice concatenation** (preferred):
```python
content = content[:old_start] + NEW_PROMPT + content[old_end:]
```

2. **Include the closing delimiter in old_end:**
```python
old_end = content.find('\n\n# ── Next section', old_start)  # skip the """ entirely
old_block = content[old_start:old_end]  # includes the """
```

3. **Fix after the fact:**
```python
content = content.replace('""""""\n', '"""\n')
```

**Detection:** `grep '""""""' server.py` or check the file visually around the point where two triple-quoted strings meet.

## Problem 3: `f"""` Strings with Nested Braces

**Symptom:** `SyntaxError: unterminated string literal` inside an `f"""..."""` block, especially with JSON examples.

**Root cause:** Python 3.12+ has a rewritten f-string parser (PEP 701). `f"""` strings with nested `{...}` expressions, `{{...}}` escaped braces, and `#` inside JSON-like content can confuse the parser. The specific trigger is often a `'` (single quote) inside an `f"""` string — Python might interpret the `'` as an opening quote if the parser loses track of which construct it's inside.

**Prevention:**
- Don't nest `f"""` inside blocks that also use `"""`. Use regular string concatenation for multi-format scenarios.
- Only use `f"""` when you actually need `{variable}` substitution.
- Test with `py_compile.compile()` before committing — Python 3.14's parser is stricter than older versions.
- When in doubt, extract the f-string into a normal `"""` string and use `.format()` instead.
