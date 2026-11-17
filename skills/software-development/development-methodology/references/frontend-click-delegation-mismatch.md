# Frontend Click Delegation Mismatch

## The Bug

Dropdown items render with `data-lid`, `data-lname`, etc. attributes on each `<div>`, but the click handler queries `closest('[data-idx]')` — a selector that never matches anything. Zero clicks are handled.

```javascript
// HTML: each dropdown item
'<div data-lid="' + l.id + '" data-lname="' + esc(l.name) + '" ...>' + ...

// Click handler (BROKEN — wrong selector)
drop.addEventListener('click', function(e) {
    var el = e.target.closest('[data-idx]'); // ❌ data-idx doesn't exist
    // el is always null → nothing happens
});
```

## Root Cause

Inconsistent naming between the data attribute used in the HTML (`data-lid`) and the selector in the click handler (`[data-idx]`). This is a copy-paste error — likely adapted from a different autocomplete that used `data-idx` + a `_leadsData` array.

## Detection

- Dropdown appears on typing ✅
- Each item renders correctly ✅
- Items are NOT clickable ❌ — no response at all
- No JS errors in console (silent failure: `closest` returns null, early return)

## Fix

Match the selector to the actual data attribute:

```javascript
// Fix 1: query the attribute that actually exists
var el = e.target.closest('[data-lid]');
if (!el) return;
var id = el.getAttribute('data-lid');
var name = el.getAttribute('data-lname');
// ... etc
```

OR use the `this.getAttribute()` inline onclick pattern (zero escaping):

```javascript
'onclick="handler(this.getAttribute(\'data-lid\'),this.getAttribute(\'data-lname\'),...)"'
```

## Prevention

1. **When adapting a working pattern, verify ALL attribute names.** A `data-idx` → `data-lid` rename must be applied everywhere.
2. **Test the click path.** After building a dropdown, open browser console and click an item. If nothing happens, the click handler is broken.
3. **Prefer `this.getAttribute()` in onclick** over addEventListener + closest. It's simpler, works immediately, and fails loudly (JS error if function doesn't exist) rather than silently.
