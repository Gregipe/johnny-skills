# JS Escaping in ARA Python Triple-Quoted Strings — Debug Workflow

The ARA dashboard embeds ~112KB of JavaScript inside a Python `"""..."""` string in `dashboard_template.py`. This creates a two-layer escaping problem:

1. **Python layer**: Python interprets escape sequences inside `"""..."""`
2. **JS layer**: The output JavaScript string literals need their own escaping

## Common Escaping Pitfalls in `"""..."""`

| Python source | Rendered in JS | Why | Fix |
|---|---|---|---|
| `\'` | just `'` | Python consumes `\` as quote escape | `\\'` in Python → `\'` in JS |
| `\n` | actual newline (0x0A) | Python interprets `\n` as newline | `\\n` in Python → `\n` in JS |
| `\\'` | `\'` | `\\` → `\`, `'` → `'` | Correct for JS apostrophe escape |
| `\\n` | `\n` | `\\` → `\`, `n` → `n` | Correct for JS newline escape |
| `\\\\'` | `\\'` | `\\\\` → `\\`, `'` → `'` | Too many — JS sees literal `\\` |

**Memory aid:** You want a single backslash in the JS output. Python needs `\\` to produce one backslash. So double the backslash for every layer: JS needs `\\'` for an escaped apostrophe → Python needs `\\\\'`. JS needs `\n` → Python needs `\\n`.

**Exception — `&apos;` HTML entity approach (no escaping needed):**
```python
# No backslashes at all — &apos; survives all layers
'<button onclick="showDealDetail(&apos;' + d.id + '&apos;)">View</button>'
```
Browser parses `&apos;` → `'` in the onclick attribute → valid JS. This is the safest approach for inline onclick handlers.

## Debug Workflow (Using Node.js)

When the sidebar `showPage()` calls don't work or the entire JS block is dead:

### Step 1: Check if JS compiles
```bash
curl -s http://localhost:8766/dashboard > /tmp/page.html
python3 -c "
import re
open('/tmp/j.js','w').write(re.search(r'<script>(.*?)</script>', open('/tmp/page.html').read(), re.DOTALL).group(1))
"
node --check /tmp/j.js
```
If `node --check` errors, the entire JS block is dead — no `showPage`, no navigation, no rendering.

### Step 2: Decode the error
Common `node --check` errors and their actual meaning:

| Error | Meaning | Fix |
|---|---|---|
| `Unexpected identifier 's'` | `'` in `Ava's` terminated the string early; `s` is unexpected | Escape the apostrophe: `Ava\\'s` in Python |
| `Unexpected identifier 'learnings'` | `'` in `showPage('learnings')` terminated the string | Use `&apos;` or `\\'` |
| `Invalid or unexpected token` | `\n` became actual newline (0x0A) split across lines | Double backslash: `\\n` in Python |

### Step 3: Byte-level inspection of the Python source

When the line number in `node --check` doesn't match the Python source line (because the JS spans many lines), use byte-level scanning:

```python
with open("dashboard_template.py", "rb") as f:
    lines = f.read().split(b'\n')
    suspect_line = lines[LINE_NUMBER - 1]  # convert 1-indexed
    idx = suspect_line.find(b"PATTERN")
    for j in range(idx, min(len(suspect_line), idx+15)):
        print(f"  byte {j}: 0x{suspect_line[j]:02X} {repr(chr(suspect_line[j]))}")
```

Look for: `0x5C 0x27` (single backslash + quote — Python will consume the backslash). You want `0x5C 0x5C 0x27` (double backslash + quote).

### Step 4: Check if JS functions are available in browser

```javascript
// In browser console or Playwright evaluate():
typeof window.showPage  // should be 'function'
typeof window.renderDashboard  // should be 'function'
```

If `undefined` for ALL functions, the entire JS block has a syntax error — see Step 1.

### Step 5: Binary fix for systematic escaping issues

When the file has multiple `\'` instances that all need doubling:

```python
with open("dashboard_template.py", "rb") as f:
    content = bytearray(f.read())

# Fix: every \' (0x5C 0x27) becomes \\' (0x5C 0x5C 0x27)
# But skip already-doubled cases (preceded by another 0x5C)
i = 0
while i < len(content) - 1:
    if content[i] == 0x5C and content[i+1] == 0x27:
        if i == 0 or content[i-1] != 0x5C:
            content.insert(i, 0x5C)  # insert another backslash
            i += 2
            continue
    i += 1

with open("dashboard_template.py", "wb") as f:
    f.write(content)
```

**Warning:** This catches ALL `\'` patterns including legitimate ones. The `\n` pattern (0x5C 0x6E) is NOT affected since the check is for `0x5C 0x27` specifically.

### Step 6: Verify fix
1. Restart server (Python module caches — `pkill -f "python.*8766"` then restart)
2. Re-step 1 (fetch + node --check)
3. Browser test: navigate, click sidebar items, verify `typeof showPage === 'function'`
