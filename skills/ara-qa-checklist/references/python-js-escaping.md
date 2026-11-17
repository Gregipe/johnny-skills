# Python → JavaScript Escaping in Triple-Quoted Strings

## The Core Problem

Inside Python triple-quoted strings (`"""..."""`), backslash sequences are processed by Python's string parser before the output reaches the browser. Three layers of interpretation stack up, and each can eat or mangle escape characters.

## The Three-Layer Stack

| Layer | What processes it | Example |
|-------|-----------------|---------|
| **L1: Python source** | Python's string parser reads the `.py` file bytes | `\\'` in the file |
| **L2: Python string value** | The actual string at runtime after all escapes are processed | `\'` in memory |
| **L3: JavaScript parse** | The browser's JS engine reads the text inside `<script>` | `\'` inside a `'...'` string keeps the string open |

Everything flows from L1 → L2 (Python parses the file) → rendered to HTML → L3 (browser parses JS).

## Escaping Table (Inside `"""..."""` Triple-Double-Quoted Strings)

| L1: File bytes | L2: Python string value | L3: What JS parses | Result |
|---------------|----------------------|-------------------|--------|
| `\'` | `'` (Python escape consumed) | bare `'` closes the JS string | **BROKEN** |
| `\\'` | `\'` (backslash preserved, quote is literal) | `\'` = escaped quote, string continues | **CORRECT** — but see note below |
| `\\\'` | `\'` (can't have three backslashes — `\\` → `\`, `\'` → `'`) | `\'` then `'` closes string | **BROKEN** — adjacent `'` |
| `\\\\'` | `\\'` (two backslashes + quote) | `\\'` = escaped backslash, then string closes | **BROKEN** — gets `\` then `'` |
| `'ve` | `'ve` | `'ve` = identifier (not string continuation) | **BROKEN** |
| `\\x27` (hex escape) | `'` (Python eats hex escapes same as `\\n`, `\\t`) | bare `'` closes the JS string | **BROKEN** — see note below |
| `\\\\x27` | `\\x27` (backslash preserved, hex preserved) | JS interprets `\\x27` as `'` inside string | **CORRECT** |

**Key insight about `\\'`:** In a `"""..."""` string, `\\'` works like this:
- `\\` → Python escape → produces one backslash `\` in the string value
- `'` → literal single quote character inside `"""` → just `'`
- Result at L2: `\'` (two characters: backslash + quote)
- At L3 inside a JS `'...'` string: `\'` is an escaped single quote → string continues

**This is the CORRECT escape for including a literal `'` inside a JS single-quoted string when building HTML inside a Python `"""..."""` block.**

## The Adjacent-String-Literal Trap (From This Session)

The MOST insidious failure pattern:

```python
# Inside DASHBOARD_HTML = """...""":
h += ' onchange="toggleIntegration(this, \\'' + ix.id + '\\')">'
```

Python processes `\\'` → `\'` at L2 (correct). But then the NEXT `'` after the first `\\'` is just a regular quote character:

- L2 value: `' onchange="...toggleIntegration(this, \'' + ix.id + '\'...'`
  - `\'` = backslash + quote in the Python string
  - The `'` that follows is also a quote character
  - So at L2: `\''` produces `\'` followed by `'`... the `\'` is the Python string content, and then `'` is just another `'` character

Wait, let me be more precise. The Python source code inside `"""..."""` contains:
```
\\'' + ix.id + '\\'
```

Parsing by Python's string parser:
- `\\` → `\` (one backslash)
- `'` → `'` (one single quote)
- `'` → `'` (another single quote — this is the one that starts ` + ix.id + `)
- ... ` + ix.id + ` ...
- `'` → `'` (one single quote — this is the one that ends ` + ix.id + `)
- `\\` → `\` (one backslash)
- `'` → `'` (one single quote)

So at L2 (Python string value): `\' ' + ix.id + ' \'`

In the rendered HTML, inside the JS `<script>`:
```javascript
'...toggleIntegration(this, \'' + ix.id + '\')...'
```

**JS parser sees:** `\'` (escaped quote — doesn't end string), then `'` (ends the JS string), then `'` (starts a new empty string). So we get adjacent string literals `'...\'...'` + `'...'` with NO operator between them.

**JavaScript does NOT support implicit string concatenation in expression contexts.** `"a" "b"` is a `SyntaxError: Unexpected string`. This is different from some other languages.

## Correct Patterns

### Pattern A: Simple concatenation (no escaped quotes needed)

When your onclick handler just needs the variable, NOT wrapped in quotes:

```python
# Python source inside """...""":
h += ' onchange="toggleIntegration(this, ' + ix.id + ')">'
```

- L1: `' + ix.id + '` — just bare single quotes
- L2: `' + ix.id + '` — same, no escaping needed
- L3 (JS): `'...this, ' + ix.id + ')...'` — string closes at `'`, expression, string opens at `'`
- Works because there's a `+` operator between the strings

### Pattern B: JS template literals (RECOMMENDED for complex HTML building)

Backticks (`) pass through Python `"""` strings unchanged and don't need escaping:

```python
# Python source inside """...""":
h += `<input type="checkbox" onchange="toggleIntegration(this, '${ix.id}')">`
```

- No escaping at any layer
- Single quotes inside the template literal are just regular characters
- `${ix.id}` is a JS interpolation — no concatenation needed
- **This is the safest pattern for generating HTML with dynamic values from JS variables**

### Pattern C: Event delegation (avoid inline onclick entirely)

```python
# In the HTML template:
h += '<input type="checkbox" class="int-toggle" data-id="' + ix.id + '">'

# In the main script block:
document.getElementById('container').addEventListener('click', function(e) {
  var toggle = e.target.closest('.int-toggle');
  if (toggle) toggleIntegration(toggle, toggle.dataset.id);
});
```

- HTML becomes static (no inline JS to escape)
- All JS lives in one script block
- No escaping issues at all

## Debugging Methodology (Binary-Level)

When you suspect escaping issues, go directly to the bytes:

```bash
# Step 1: Check what the file ACTUALLY has on disk
sed -n '440p' dashboard_template.py | xxd | head -8
# Look for: 5c 27 = backslash + quote, 5c 5c = two backslashes, 27 = bare quote

# Step 2: Check what Python's string value produces
cd /project && source venv/bin/activate
python3 -c "
from dashboard_template import DASHBOARD_HTML
idx = DASHBOARD_HTML.find('targetFunction(')
chunk = DASHBOARD_HTML[idx:idx+60]
for i, c in enumerate(chunk):
    print(f'{i:3d}: {ord(c):3d} (0x{ord(c):02x}) {repr(c)}')
"

# Step 3: Extract the JS and validate with node
python3 -c "
from dashboard_template import DASHBOARD_HTML
start = DASHBOARD_HTML.index('<script>') + 8
end = DASHBOARD_HTML.index('</script>')
with open('/tmp/check.js', 'w') as f:
    f.write(DASHBOARD_HTML[start:end])
"
node -c /tmp/check.js

# Step 4: Check rendered output via HTTP
curl -s http://localhost:8766/page | grep 'targetFunction' | xxd | head -5
```

## Byte-Level Fix Script Pattern

When you need surgical byte-level replacement (the `patch` tool can't handle escaping chains):

```python
with open('file.py', 'rb') as f:
    data = f.read()

# Find exact bytes to replace
old = bytes([0x5c, 0x27, 0x27, 0x20, 0x2b, ...])  # \' ' + ...
new = bytes([0x27, 0x20, 0x2b, ...])  # ' + ...

data = data.replace(old, new)
with open('file.py', 'wb') as f:
    f.write(data)
```

## The Full Rendering Pipeline Check

When diagnosing a bug:
1. **File bytes** → `sed -n 'LINEp' file.py | xxd` — what's actually on disk
2. **Python string value** → `repr(DASHBOARD_HTML[idx:idx+N])` — what Python turned it into
3. **Rendered HTML** → `curl http://localhost/ ...` — what the web server sends
4. **JS execution** → `node -c /tmp/check.js` — does the JS parse correctly?
5. **Browser runtime** → check `browser_console` for empty JS errors

## Common Failure Patterns

1. **`'ve`, `'s`, `'ll`, `'re`** — Contractions break single-quoted JS strings. Reword: "You have" not "You've", "it is" not "it's"
2. **`\' + var + \'`** — Produces `\'escaped-quote` then `'string-close` then `'new-string`, creating adjacent literals. Use template literals or simple `' + var + '` instead
3. **`onclick="fn(' + var + ')"` inside `'...'` JS string** — The `' + var + '` creates valid concatenation WITH the `+` operator between them, avoiding adjacent literals. This is actually correct.
4. **Double-escaping** — `\\'` in the file → Python produces `\'` → JS reads as escaped quote → STRING STAYS OPEN. Usually not what you want.
5. **Contractions inside triple-quote strings that are NOT in JS code** — If the contraction is in plain HTML text (not inside a `<script>` tag or onclick), Python keeps `'` as-is, which is fine in HTML.
6. **`\\x27` hex escapes are consumed by Python** — Python processes `\\x27`, `\\x22`, `\\n`, `\\t`, etc. inside triple-quoted strings the same way. `\\x27` produces the literal `'` character (U+0027), NOT the four bytes `\\x27` in the output. If your intent is to output `\\x27` so JS can interpret it as `'` inside an escape sequence, the Python source must have `\\\\x27` (double backslash). Check with `grep -n 'x27' dashboard_template.py` — if you see `\\x27` (single backslash), Python will eat it. You need `\\\\x27` (double backslash) instead.

## Best Practice

When embedding HTML/JS inside Python `"""..."""` strings:

1. **Use JS template literals (backticks)** for any line that builds HTML with dynamic values. Backticks pass through Python unchanged and make `${var}` interpolation trivial.
2. **Use `addEventListener`** instead of inline `onclick` attributes — move all event wiring to the main script block.
3. **Use double quotes for JS strings** when you can't use backticks: `'msg += "Hello" + name + ""'` — no quote collision with Python's `"""`.
4. **Never use contractions** (You've → You have, That's → That is, I'll → I will, We're → We are).
5. **Verify with `node -c`** after any JS change inside Python strings.
6. **Debug with `xxd` + `repr()` + byte-level slicing** — the `patch` tool can't handle escaping chains; use a Python script with `bytes.replace()` instead.
