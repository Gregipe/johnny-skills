# Patch Tool: Unicode Escape Edge Case

## The Problem

When unicode escapes are stored as **double-escaped literal strings** in Python source files (e.g., `\\u2726` in the Python source represents the literal characters `\u2726`, which renders as ✦ at runtime), the `patch` tool's fuzzy matching cannot find the string.

## Example

In `/Users/greg/ara/server.py` line 7747:

```python
formatted = "\\u2726 *Ava :*\\n\\n" + ava_reply
```

The `patch` tool receives `content.replace(old_string, new_string)` with `old_string = "\u2726"` but the file contains `\\u2726` (literal backslash-u-2-7-2-6). The match fails even with fuzzy matching because the source bytes are different: `\` followed by `u` (two characters) vs the actual Unicode character ✦ (one codepoint).

## Diagnosis

Use Python or hex inspection to find out what the file actually contains:

```bash
python3 -c "
with open('/path/to/file.py') as f:
    lines = f.readlines()
for i, line in enumerate(lines, 1):
    if '\\u2726' in repr(line):
        print(f'Line {i}: {repr(line)}')"
```

Key: if `repr()` shows `\\u2726` (double backslash), the file contains the literal escape sequence, not the rendered Unicode character.

## Fix: Use Python String Replacement

Use `content.replace()` with the correct escape level:

```python
path = '/path/to/file.py'
with open(path) as f:
    content = f.read()
# The file contains literal \\u2726 (two chars: backslash + u2726)
content = content.replace('\\\\u2726 *Ava :*', '\\\\u2728 *Ava :*')
with open(path, 'w') as f:
    f.write(content)
```

**Important:** In Python source code, to match the literal bytes `\u2726` in the file, you need `\\\\u2726` in the `.replace()` call (each `\\` in the source file needs `\\\\` in the Python string literal).

## Prevention

When storing unicode escapes in Python source code, consider using the raw Unicode character directly instead of the escape sequence:

```python
# Harder to edit with patch tool:
formatted = "\\u2728 *Ava :*\\n\\n" + ava_reply

# Easier to edit with patch tool:
formatted = "✨ *Ava :*\n\n" + ava_reply
```

However, some teams prefer the explicit escape form for portability across editors/encodings. In those cases, note that `patch` tool edits require the Python `content.replace()` workaround.
