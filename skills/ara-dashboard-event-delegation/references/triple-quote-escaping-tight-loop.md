# Triple-Quote Escaping Tight Loop

## The Session Problem

Building `startLeadChat()` inside `dashboard_template.py`'s triple-quoted string. The function included JS string literals with `\n` newline escapes. Three iterations of escaping hell with three different approaches.

## Iteration 1: `\'` inline onclick (BROKEN)

```python
# In the Python """...""" string:
'<button onclick="startLeadChat(\'' + l.id + '\')">'
```

**Result:** The `\'` in the Python string becomes just `'` (Python consumes the backslash). The `'` closes the outer JS string. Syntax error.

**Fix:** Switch to `data-action` + event delegation.

## Iteration 2: `\\n` in JS strings (BROKEN)

```python
# In the Python """...""" string, trying to produce a JS \n escape:
? 'Past interactions:\\n' + data.conversations...
```

**Result:** `\\n` in a Python triple-quoted string becomes `\n` (2 bytes: 0x5C + 0x6E). This IS the correct JS escape for newline. BUT — the hex dump showed `0x0A` (actual newline) in the HTML output. 

**Root cause:** The patch tool's `new_string` parameter passing. Writing `\\n` in the patch parameter → file gets `\n` (single backslash) → Python `"""..."""` treats as newline escape → actual newline in HTML.

**Fix:** Write `\\\\n` (4 backslashes) in the patch parameter → file gets `\\n` (2 backslashes) → Python `"""..."""` outputs `\n` (1 backslash) in HTML → valid JS.

## Iteration 3: Binary replacement (NUKE IT)

When the patch tool's escaping produces inconsistent results:
```python
with open('/path/to/file.py', 'rb') as f:
    data = f.read()
# Replace single \n (0x5C 0x6E) with double \\n (0x5C 0x5C 0x6E)
data = data.replace(b'\\n', b'\\\\n')
with open('/path/to/file.py', 'wb') as f:
    f.write(data)
```

## Debugging Checklist

When `node --check` fails on a file built from a Python triple-quoted string:

1. `curl -s http://localhost:8766/PAGE > /tmp/page.html`
2. `node --check <(python3 -c "import re; open('/tmp/j.js','w').write(re.search(r'<script>(.*?)</script>', open('/tmp/page.html').read(), re.DOTALL).group(1))")` — find exact error line
3. `sed -n 'LINE_NUMBERp' /tmp/j.js | xxd` — check hex for:
   - `5c 6e` = `\n` (single backslash-n — WRONG inside """ """ for JS)
   - `5c 5c 6e` = `\\n` (double backslash-n — CORRECT inside """ """ for JS)
   - `0a` = actual newline (WRONG — Python ate the escape)
4. If the Python file has `\n` (single backslash), Python `"""..."""` evaluates it as a newline escape
5. If the Python file has `\\\\n` (4 backslashes), Python evaluates `\\\\` as `\\` (double backslash) → produces `\\n` in HTML — wrong for JS
6. The file should have `\\n` (2 backslashes) — Python evaluates `\\` as `\` → produces `\n` in HTML ✅
