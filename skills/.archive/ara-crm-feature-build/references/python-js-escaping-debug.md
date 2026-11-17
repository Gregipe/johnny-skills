# Debugging Python-JS Escaping in ARA Dashboard Templates

How to trace and fix JS syntax errors caused by Python's `"""..."""` string processing in the ARA dashboard template.

## The Problem

The ARA dashboard is a single giant Python triple-quoted string (`DASHBOARD_HTML = """..."""`). Inside it, JavaScript builds HTML via `innerHTML`, and that HTML has `onclick` handlers with string arguments. Five layers of escaping:

```
Python source file → Python """...""" string → rendered HTML/JS → JS string → innerHTML → HTML onclick attribute → JS callback code
```

The critical failure mode: **Python consumes `\'` as an escape sequence**. Inside `"""..."""`, `\'` → just `'` (the backslash disappears). This causes `'` inside JS string literals to leak out and terminate strings prematurely.

## Patch-Tool Backslash Doubling

**New failure mode:** The `patch` tool can double backslashes when editing Python raw strings containing JS. When you patch a line like `Hunar\'s` (valid JS — escaped apostrophe), the patch tool may write `Hunar\\'s`, doubling the backslash.

**Why this breaks JS:** In the source file `Hunar\\'s` produces JS text `Hunar\\'s`, which JS reads as: escaped backslash (`\\` → literal `\`), then `'` **terminates the string**. The `s` that follows becomes an unexpected identifier.

**Detecting this:** `node --check` reports `"Unexpected identifier 's'"` or `"Unexpected identifier 've'"` — these are the characters that follow the doubled apostrophe.

## Diagnostic Workflow

### 1. Grab the rendered page

```bash
curl http://localhost:8766/dashboard > /tmp/page.html
```

### 2. Extract the script and check with node

```bash
python3 -c "
import re
open('/tmp/j.js','w').write(
    re.search(r'<script>(.*?)</script>',
        open('/tmp/page.html').read(), re.DOTALL).group(1)
)"
node --check /tmp/j.js
```

`node --check` exits 0 if clean. If it fails, it reports the exact line and caret position.

### 3. Examine the reported line

```python
# Line N (1-indexed) from the JS file
python3 -c "print(repr(open('/tmp/j.js').read().split('\n')[N-1]))"
```

### 4. Byte-level analysis to trace escaping

When `node --check` points at a suspicious area, examine the actual bytes:

```python
with open('/tmp/j.js', 'rb') as f:
    data = f.read()

# Find the problematic string in the rendered output
idx = data.find(b'showDealDetail')
snippet = data[idx:idx+80]

# Print every byte with character and code
for i, b in enumerate(snippet):
    ch = chr(b) if 32 <= b < 127 else '?'
    print(f'  byte {i}: {b} (0x{b:02x}) = {repr(ch)}')
```

### 5. Byte-level inspection of the SOURCE file (Python raw string)

When the extracted JS looks correct but you suspect the source file itself has doubled backslashes, inspect the Python file directly at the byte level:

```python
with open('/Users/greg/ara/cadence_template.py', 'rb') as f:
    data = bytearray(f.read())

# Find suspect strings and count backslash bytes
idx = data.find(b'Hunar')
while idx >= 0:
    # Count consecutive 0x5c (backslash) bytes after the string
    backslashes = 0
    pos = idx + 5
    while pos < len(data) and data[pos] == 0x5c:
        backslashes += 1
        pos += 1
    print(f"Hunar at pos {idx}, followed by {backslashes} backslashes, next char: {chr(data[pos]) if pos < len(data) else 'EOF'}")
    idx = data.find(b'Hunar', idx + 1)
```

**Expected patterns:**
- `5c 27` (one backslash + apostrophe) → JS sees `\'` → escaped quote → CORRECT
- `5c 5c 27` (two backslashes + apostrophe) → JS sees `\\'` → escaped backslash + string end → BROKEN

**Fixing doubled backslashes at byte level:**
```python
with open('/Users/greg/ara/cadence_template.py', 'rb') as f:
    data = bytearray(f.read())

# Fix: remove one backslash from each doubled pair
idx = data.find(b"We\\\\'ve")
if idx >= 0:
    # We + 2 backslashes + 've → We + 1 backslash + 've
    data[idx:idx+7] = data[idx:idx+4] + b"\\'ve"

with open('/Users/greg/ara/cadence_template.py', 'wb') as f:
    f.write(data)
```

### 6. Trace through JS string parsing

For each `'` in the rendered JS that's supposed to be inside a `'...'` string literal, check:

- **Single backslash `\'`**: In JS, valid escaped quote → literal `'` inside the string. ✓
- **Double backslash `\\'`**: `\\` is escaped backslash → literal `\`, then `'` ENDS the string. ✗
- **No backslash `'`**: Ends the string. ✗ (unless that's the intended end)

### 7. Binary search for the error

If `node --check` fails but the line is unhelpful:

```bash
# Remove lines near the error to see if it moves
python3 -c "
lines = open('/tmp/j.js').readlines()
del lines[N-1]  # Remove suspect line
open('/tmp/j2.js', 'w').writelines(lines)
"
node --check /tmp/j2.js
# If the error moves to a similar pattern on another line,
# you've identified the class of issue
```

### 8. Server restart after source fix

The Python module is cached in memory. After fixing the `.py` source file:

```bash
kill <server_pid>
# Restart — the module re-imports fresh CADENCE_HTML/DASHBOARD_HTML
cd /Users/greg/ara && /Users/greg/.hermes/hermes-agent/venv/bin/python3.11 server.py &
```

Then re-run steps 1-3 to verify the fix.

## The Three Fixes (in preference order)

### Fix #1 — Event Delegation (PREFERRED)

Eliminates inline onclick entirely — no escaping needed.

**Python template:** Use `data-*` attributes:
```python
html += '<div class="deal-card" data-id="' + d.id + '">'
```

**JS:** Single delegated listener:
```javascript
document.getElementById('centerPanel').addEventListener('click', function(e) {
    var card = e.target.closest('.deal-card');
    if (card) showDealDetail(card.dataset.id);
});
```

### Fix #2 — `&apos;` HTML Entity

For inline onclick with string arguments, use `&apos;` (HTML entity for `'`). It survives all five layers with zero backslashes:

```python
# Python source — no escaping needed
html += '<button onclick="editDealStage(&apos;' + d.id + '&apos;)">Move Stage</button>'
```

Browser parses `&apos;` → `'` when the HTML is inserted into the DOM, so the onclick handler sees: `editDealStage('123')` — valid JS.

### Fix #3 — CSS for visual effects

Replace `onmouseover`/`onmouseout` color changes with CSS `:hover`:

```css
.deal-card-hoverable { border-color: #E5E5E7; transition: border-color 0.1s; }
.deal-card-hoverable:hover { border-color: #D0D0D5; }
```

## Common `node --check` Error Messages

| Error | Meaning |
|-------|---------|
| `Unexpected identifier 's'` | After a doubled backslash + apostrophe — the `'` terminated the string, `s` is an unexpected identifier |
| `Unexpected identifier 've'` | Same pattern with `We\'ve` → `We\\'ve`, the `'ve` part is now outside the string |
| `Unexpected identifier '#D0D0D5'` | A `#` color code leaked outside a string — the `'` before it ended the JS string |
| `Unexpected string` | A stray string literal outside any expression — `'` ended a string prematurely and the `'` after it started a new one in the wrong place |
| `Unexpected token ')'` | Bare `)` outside function call — JavaScript string ended too early and the `)` is now in expression context |

## Verification Checklist

After fixing, verify in this order:

1. `node --check /tmp/j.js` — exits 0
2. `curl http://localhost:8766/dashboard | python3 -c "import sys; d=sys.stdin.read(); print('showPage' in d and 'renderDeals' in d and 'showDealDetail' in d)"` — all True
3. `browser_console(expression='typeof showPage')` — returns `"function"`
4. Click through nav items — each page renders without console errors
5. `browser_console` — empty (no JS errors)
6. Check localStorage data integrity — `browser_console(expression='localStorage.getItem("ara_cadence_data")')` — JSON should parse, no corruption
