# `window.open()` Quoting Trap

## Symptom
Browser console reports `SyntaxError: Unexpected string`. All JS after a certain point in the script is dead — `showPage`, `renderDashboard`, etc. are all undefined.

No obvious inline onclick in the source code you wrote. The error points to a line inside a JS string literal concatenation.

## Reproduction

In `dashboard_template.py`, inside `renderInduction()`, building HTML via innerHTML string concatenation:

```javascript
'<button class="ind-continue-btn" onclick="window.open(\'/induction/chat/3e736242\', \'_blank\')">Continue</button>'
```

The rendered browser output (after Python triple-quoted string processing):

```html
'<button class="ind-continue-btn" onclick="window.open('/induction/chat/3e736242', '_blank')">Continue</button>'
```

The `'` before `/induction` closes the outer JS string literal. Everything after is garbage.

## Root Cause Chain

1. Python `DASHBOARD_HTML = """..."""` — the outer Python string
2. Inside it, the render function builds HTML as JS string literals: `'...' + var + '...'`
3. The `onclick` attribute needs single quotes for the JS arguments: `window.open('/path', '_blank')`
4. In Python, you escape those inner single quotes with `\'` — but Python's triple-quoted string eats the backslash
5. The rendered HTML has bare single quotes in the onclick value
6. The **outer** JS string literal (delimiter `'`) hits that `'` and terminates prematurely
7. JS parser sees `...onclick="window.open('` followed by `/induction/...` — the `/` is an unexpected token

## Fix

Use event delegation instead. Replace `onclick` with `data-action`:

```javascript
// BEFORE (breaks):
'<button class="ind-continue-btn" onclick="window.open(\'/induction/chat/3e736242\', \'_blank\')">Continue →</button>'

// AFTER (works):
'<button class="ind-continue-btn" data-action="continue-induction">Continue →</button>'
```

Then in the event delegation handler:

```javascript
if (action === 'continue-induction') {
  window.open('/induction/chat/3e736242', '_blank');
  return;
}
```

## Verification

1. Run `node --check` on the extracted JS — should pass cleanly
2. Load the dashboard and click the Induction page
3. Click "Continue Induction" — opens in new tab
4. No console JS errors throughout

## Lesson

**Any inline `onclick` containing single-quoted arguments inside a JS innerHTML string literal will break.** The pattern `window.open('/path', '_blank')` with two comma-separated single-quoted args is a particularly common variant that looks different enough from `func('arg')` that you might not connect it to the same root cause.

When you need:
- Navigate on click → use `window.location.href = url` in delegation handler
- Open new tab → use `window.open(url, target)` in delegation handler
- Any function call with string arguments → use data attributes for the args
