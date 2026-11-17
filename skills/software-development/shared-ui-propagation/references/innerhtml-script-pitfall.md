# innerHTML + Script Tags: The Silent Failure

## The Problem

Browsers **do not execute `<script>` tags injected via `innerHTML`**. This is a security feature (HTML5 spec §4.12.1). Any dynamically-loaded content that depends on inline scripts will silently fail — no error, no console warning, just broken behavior.

## How it fails

```javascript
// ❌ NEVER WORKS — script never executes
cp.innerHTML = '...<script>loadActionsForLead(id);</script>';

// The page renders the HTML but the <script> is dead
// User sees "Loading actions…" forever
```

## The Fix

Call the function directly after setting `innerHTML`:

```javascript
// ✅ Correct
cp.innerHTML = '...';
loadActionsForLead(id);
```

## Why it's hard to catch

- No syntax error — the JS file parses fine
- No runtime error — the browser silently ignores the script tag
- The HTML markup looks correct in DevTools
- Node `--check` passes (the JS syntax is valid)
- The function exists — it just never gets called

## Detection

If you see "Loading…" text that never updates, or content that clearly depends on a JS function but nothing happens, suspect this bug.

## Rule

**Never embed `<script>` tags in `innerHTML` strings.** Always call the initialization function on the line after the `innerHTML` assignment.
