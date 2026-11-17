# JavaScript Escaping in Python-Generated HTML

## The Problem

When Python code writes JavaScript that itself generates HTML containing inline `onclick` handlers, the `\'` escape sequence breaks catastrophically. This is the single most common cause of "page goes blank / nothing is clickable" in ARA.

### How it breaks

```javascript
// Python writes this JS string:
container.innerHTML = '...onclick="showAddActionForm(\' + leadId + \')"...

// The JS parser sees the \'  as an escaped single-quote
// The second single-quote CLOSES the outer JS string EARLY
// Result: SyntaxError — Invalid or unexpected token
// The ENTIRE JS file fails to parse — page blank
```

### Why it's insidious

- **Node `--check` catches it** — but only if you run it before deploying
- **The server returns 200 OK** — FastAPI serves the file fine; the error is client-side
- **No browser console error visible** — the `<script>` tag simply never executes
- **Every JS function on the page is dead** — leads, deals, activities, all gone

## The Fix: Data Attributes

Never embed dynamic values in `onclick` via string concatenation. Use `data-` attributes:

```javascript
// ❌ BROKEN — \'  escape inside JS string inside HTML attribute
container.innerHTML = '...onclick="showAddActionForm(\' + leadId + \')"...';

// ✅ CORRECT — data- attribute, accessed via this.dataset
container.innerHTML = '...data-lead-id="\' + leadId + \'" onclick="showAddActionForm(this.dataset.leadId)"...';
```

The `data-` approach:
- Avoids all escaping issues (no quotes to break)
- Works in every browser
- The JS function signature stays clean: `showAddActionForm(leadId)` → `showAddActionForm(this.dataset.leadId)`

## Detection

Run before deploying any `.js` file change:
```bash
node --check static/dashboard.js
```

If it fails, the exact line and position are in the error output.

## The `&#39;` Trap

Using HTML entities (`&#39;`) instead of `\'` looks clever but FAILS:

```javascript
container.innerHTML = '...onclick="showAddActionForm(&#39; + leadId + &#39;)"...'
```

The browser unescapes `&#39;` → `'`. But that `'` is now a JS string delimiter inside the onclick handler, CLOSING the outer JS string. Same crash, different syntax.

## Never: Pre-Escaping in Python

Writing `\\\\'` (four backslashes) in the Python source doesn't help — it just adds noise. The root issue is string-in-string-in-string escaping. Data attributes break the nesting entirely.
