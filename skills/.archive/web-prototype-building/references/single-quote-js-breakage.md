# Single-Quote Breakage in Python-Rendered JS

## Reproduction Recipe

When inline JavaScript is embedded in a Python `"""..."""` string, Python's escape processing runs BEFORE JS gets the code. This creates a class of silent breakage where `\'` looks correct to human eyes (it's how you escape a quote in JS!) but Python has already consumed the backslash.

## The Bug

**File:** `dashboard_template.py` (Python triple-quoted string `"""..."""`)

```python
# Line 1922 — the ONLY broken line among 14 similar patterns:
'<h3>🧠 Ava\'s Learnings<span ...>' + pending + ' to review</span></h3>'
```

**What happens:**

| Layer | Processing | Result |
|-------|-----------|--------|
| Python `"""..."""` | Sees `\'` as recognized Python escape | `'` (bare single quote) |
| JS parser | Encounters `'` inside `'...'` string literal | **String terminated early** |
| Downstream | `s Learnings` is now syntax garbage | **Entire 132KB script fails to parse** |

**Symptom:** Sidebar nav items don't work, pages don't load, no console errors. `typeof showPage` returns `"undefined"`. Everything on the dashboard appears dead.

## Why It's Deceptive

There were 14 other `\'` instances in the same file (in onclick handler attributes like `onclick="cancelAction(\'' + a.id + '\')"`). These also produced bare `'` in the output, but `''` inside an HTML onclick attribute is valid JavaScript — it's an empty string. So they worked by accident:

```javascript
// Rendered HTML:
onclick="cancelAction('' + a.id + '')"
// JS evaluates '' as empty string → cancelAction(a.id.toString()) → works!
```

The `Ava\'s` possessive was the ONLY instance where `'` ended up inside JS string *content* rather than inside an HTML attribute. That one killed the entire script.

## The Fix

Replace `\'` with `\\x27` (double backslash + x27):

```python
# BROKEN:
'<h3>🧠 Ava\'s Learnings</h3>'

# FIXED:
'<h3>🧠 Ava\\x27s Learnings</h3>'
```

**Why `\\x27` works:**
- Python sees `\\` → outputs `\` (one backslash)
- Python sees `x27` → outputs `x27` (literal text)  
- JS sees `\x27` → hex escape → `'` (0x27)

## Verification

After any edit to inline JS in a Python template:

```bash
# 1. Serve the page and capture it
curl http://localhost:8766/dashboard > /tmp/page.html

# 2. Extract script block and validate syntax
python3 -c "
import re
m = re.search(r'<script>(.*?)</script>', open('/tmp/page.html').read(), re.DOTALL)
if m:
    open('/tmp/js_check.js','w').write(m.group(1))
    print('Extracted', len(m.group(1)), 'bytes')
"
node --check /tmp/js_check.js  # must exit 0
```

## Prevention

1. **Best:** Move JS to a static `.js` file. No Python-in-JS escaping problem.
2. **Good:** Use event delegation (`data-*` attributes + single listener) instead of inline onclick with string args.
3. **Adequate:** Use `\\x27` consistently. Never use `\'` to represent a quote in JS content.
4. **Guard:** Run `node --check` on extracted JS as a pre-commit hook or CI step.

## Root Cause

Three engineers independently wrote `\'` thinking it was a JS escape, not realizing Python `"""..."""` strings process escapes first. The pattern looks right — `\'` IS how you escape a single quote in JavaScript — but it's wrong in this context because Python strips the backslash before JS ever runs.
