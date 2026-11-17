# Adding a New Dashboard Page in ARA

The canonical workflow for adding a new page (e.g. Knowledge, Induction) to the ARA dashboard sidebar.

## Steps (in order)

### 1. CSS classes
Add page-specific CSS right before `</style>` in `dashboard_template.py`. Keep naming convention consistent with existing classes (`kb-*`, `ind-*`, `page-title`, `page-subtitle`).

### 2. Sidebar nav item
```html
<div class="nav-item" onclick="showPage('pagename')">
  <span class="icon">EMOJI</span> PageName
</div>
```
Insert in the sidebar nav, before Integrations and Threads.

### 3. showPage routing
```javascript
else if (page === 'pagename') renderPageName();
```
Add to the `showPage` function's chain of if/else-if blocks.

### 4. Render function
```javascript
async function renderPageName() {
  var cp = document.getElementById('centerPanel');
  cp.innerHTML =
    '<div class="page-title">Page Name</div>' +
    '<div class="page-subtitle">Subtitle description</div>' +
    '<div id="listContainer">...</div>';
  loadListData();
}
```

### 5. Data loading + CRUD
Write separate async functions: `loadListData()`, `createItem()`, `deleteItem()`. Use fetch to API endpoints.

### 6. Event delegation handlers
Add to the `#centerPanel` delegation handler for click actions:

```javascript
if (action === 'delete-item') { deleteItem(t.dataset.itemId); return; }
```

### 7. Non-click events (if needed)
For drag-and-drop, file inputs, or other non-click interactions, add separate document-level listeners (not part of the click delegation).

### 8. Verify
- Run `node --check` on extracted JS (no syntax errors)
- Navigate to the page via sidebar
- Test all interactive elements
- Check browser console for JS errors

## Traps

- **Inline onclick in innerHTML breaks** — see `references/window-open-quoting-trap.md`. Always use `data-action` + event delegation. This applies to ALL template files (`dashboard_template.py`, `threads_template.py`) — any file where Python `"""..."""` wraps JS that builds HTML via `html += '...'`.
- **DOM not ready** — if `document.getElementById('listContainer')` returns null, the element was created in the render function but the DOM hasn't settled yet. Either call load from inside render (after setting innerHTML) or guard with `if (!container) return;`.
- **Modals outside #centerPanel** — modals appended to `document.body` need their own click handler, not the centerPanel delegation. See `references/modal-outside-delegation.md`.
