# IIFE Scope Breaks Inline onclick Handlers (June 2026)

## Symptoms

- Dropdown menus render with correct HTML
- Clicking the ⋮ (vertical ellipsis) button does nothing — no dropdown opens
- Clicking menu items (Edit, Delete, Mark Done) does nothing
- Browser console shows NO errors — silently fails
- But other menus on the same page work fine (some use class-based, some use inline)

## Root Cause

The JavaScript file is wrapped in an IIFE (Immediately Invoked Function Expression):

```javascript
(function() {
  function editActionItem(id) { ... }
  function resolveActionItem(id) { ... }
  function deleteActionItem(id) { ... }
})();
```

HTML generated with inline `onclick` attributes:

```html
<div onclick="editActionItem('abc123')">Edit</div>
```

`onclick` handlers execute in the **global scope**. The functions `editActionItem`, `resolveActionItem`, etc. are **private** to the IIFE scope — they don't exist in the global scope. The browser silently resolves `editActionItem` to `undefined`, calls nothing, and shows zero errors.

## Fix

Convert ALL action menus to use class-based event delegation:

```javascript
// Inside the IIFE — this works because it's registered as a DOM event listener:
document.addEventListener("click", function(e) {
  var edit = e.target.closest(".am-edit");
  if (edit) {
    editActionItem(edit.getAttribute("data-aid"));
    // ...
    return;
  }
  var del = e.target.closest(".am-delete");
  if (del) {
    deleteActionItem(del.getAttribute("data-aid"));
    // ...
    return;
  }
});
```

```html
<!-- Class-based HTML — no onclick, uses data attributes: -->
<span class="am-container">
  <button class="am-toggle">&#8942;</button>
  <div class="am-dropdown">
    <div class="am-edit" data-aid="abc123">Edit</div>
    <div class="am-delete" data-aid="abc123">Delete</div>
  </div>
</span>
```

The event delegation runs inside the IIFE, so it can reach private functions. The HTML just needs data attributes — no inline JavaScript.

## Alternatives (Choose Based on Architecture)

1. **Class-based delegation** (recommended): Single listener, works with IIFE, clean HTML. Use when all menus follow the same pattern.

2. **Window export**: `window.editActionItem = editActionItem;` — Make functions global. Quick fix but pollutes global scope. Use when refactoring all menus is too expensive.

3. **Remove IIFE**: Unwrap the file. Breaks variable encapsulation. Only use if the IIFE is a mistake, not intentional isolation.

## Prevention Checklist

When adding any new interactive HTML button/menu:
- [ ] If the JS is in an IIFE → use class-based delegation, NOT inline onclick
- [ ] Verify `closest()` selector matches the exact class name in the HTML
- [ ] Verify `data-*` attribute name in HTML matches the `.getAttribute()` call
- [ ] Test by clicking before announcing it works
