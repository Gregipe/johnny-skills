# Undefined Variable in innerHTML Template String

## The Pattern

A JS function builds HTML via `html += '...'` string concatenation and assigns to `.innerHTML`. Inside the template, a variable is referenced but never defined. The browser throws a `ReferenceError`, caught by a Promise's `.catch()` → generic error message like "Error loading decks".

## Symptom

- The feature shows a generic error message instead of data
- Browser console shows a `ReferenceError` with empty or obscure message (because the error was caught by a `.catch()` handler that shows a static fallback)
- No visible stack trace unless you instrument `window.onerror` or `window.addEventListener('error', ...)` **before** the page loads

## Root Cause

A variable used inside a JS template string was supposed to be computed from API data but was never defined:

```javascript
// Inside a .then() callback iterating over API results:
decks.forEach(function(d) {
  var icon = {pdf:'📕', txt:'📄'}[ext] || '📄';
  // sourceTag was supposed to be computed from d.source here:
  // var sourceTag = d.source === 'deck' ? ' DECK' : ' KB';
  
  html += '<span class="pb-deck-sub">' + d.word_count + ' words' + sourceTag + '</span>'; // ❌ sourceTag never defined
});
```

The `ReferenceError` (`sourceTag is not defined`) is caught by the Promise's `.catch()` which renders a generic "Error loading decks" div. The user sees a broken deck selector with no indication of the real cause.

## Debugging Path

1. **Open browser console** before interacting — the error fires once when the page loads or the tab is clicked
2. Watch for `ReferenceError: X is not defined` — these get swallowed by `.catch()` handlers
3. Look at the function that `.then()` calls — find where the variable is referenced but not declared
4. Trace where the variable should have been computed from the loop data

## Precedent

This exact bug happened in `loadDeckSelector()` in `prompt_builder_template.py` (May 2026):

- `sourceTag` was used on line 1155 in `html += '...'` concatenation
- It was supposed to show "DECK" vs "KB" per document based on `d.source`
- The variable was never defined — a ReferenceError in the `.then()` callback
- The `.catch()` handler showed "Error loading decks" — misleading
- Fix: add `var sourceTag = d.source === 'deck' ? '...' : '...';` before the template string

## Prevention

When adding a section that builds HTML inside a `.then()` callback and assigns to `.innerHTML`:

1. **Check every variable** referenced in the template string is defined in the function scope
2. **Don't assume variables exist** because you "remember" writing them — verify each one
3. **Test by navigating to the tab/feature** and checking browser console — not just looking at the visible UI
4. **The `.catch()` swallows the real error** — always check the console, not just the visible "error" message

## Related

- The same pattern caused `esc()` to crash when it wasn't defined (see `references/triple-quote-escaping-tight-loop.md`)
- The debugging is harder here because the error is caught, not surfaced — always instrument `window.addEventListener('error', ...)` early
