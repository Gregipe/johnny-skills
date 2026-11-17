# Dashboard Template — Python String Escaping for JavaScript

## The Bug

`dashboard_template.py` stores the entire dashboard HTML inside a Python triple-quoted string:

```python
DASHBOARD_HTML = """<!DOCTYPE html>
... thousands of lines of HTML/JS ...
</html>"""
```

Python's triple-quoted strings (`"""..."""`) process escape sequences including `\n` → newline (0x0A). When JavaScript strings containing `\n` are written inside this Python string, Python converts `\n` to a real newline byte BEFORE the HTML is served. The browser then receives a literal newline inside a JS string literal, causing `SyntaxError: Unexpected EOF`.

## Symptom

Browser console shows:
```
[Error] SyntaxError: Unexpected EOF
[Error] ReferenceError: Can't find variable: toggleVoiceMode
```

The entire `<script type="module">` fails to parse. `window.toggleVoiceMode` is never assigned. All voice buttons become permanently dead with no visible error to the user.

## Diagnosis

Check the raw HTML output (not the Python source):
```bash
curl -s 'http://localhost:8766/dashboard' | grep 'result.split' | xxd | head -5
```

If you see `split('` followed by `0a` (newline byte), the `\n` was converted to a real newline.

Verify with Node strict module parsing:
```bash
curl -s 'http://localhost:8766/dashboard' > /tmp/dash.html
node --input-type=module --check < /tmp/module.js
```

If it fails with `Invalid or unexpected token` at the split line, the escaping is broken.

## Fix

In the Python source file, write `\\n` (double backslash) so Python preserves it as literal `\n` in the HTML output:

```python
# WRONG — Python converts \n to newline in triple-quoted string:
"result.split('\n')[0]"

# RIGHT — \\n becomes \n in HTML, which JS parses as newline escape:
"result.split('\\n')[0]"
```

The escaping chain:
1. Python source: `\\n` (2 chars: `\` + `n`)
2. Triple-quoted string processing: `\` + `n` (unchanged — `\` is an escaped backslash, not a newline prefix)
3. HTML output: `\n` (2 bytes: 0x5C + 0x6E)
4. JavaScript parsing: `'\n'` → string containing a newline character (0x0A)

## Affected Patterns

Any JavaScript string containing backslash escapes inside `DASHBOARD_HTML`:
- `'\n'` → write as `'\\n'`
- `'\t'` → write as `'\\t'`
- `'\\'` → write as `'\\\\'`
- Regular expression: `/\\s/` → write as `/\\\\s/`

## Verification

After fixing, re-verify:
```bash
ssh root@46.224.132.99 'curl -s http://localhost:8766/dashboard' | node --input-type=module --check
```

Must return no error (exit 0).
