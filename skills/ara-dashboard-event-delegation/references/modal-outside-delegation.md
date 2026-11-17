# Modal Outside Event Delegation — Bug & Fix

## Symptom
X button, Cancel button, and backdrop-click in the Add Lead modal do nothing. No console errors. The modal just stays open.

## Root Cause
A click handler is registered on `#centerPanel`:
```javascript
document.getElementById('centerPanel').addEventListener('click', function(e) { ... });
```

But the modal is appended to `document.body`:
```javascript
document.body.appendChild(modal);
```

Since the modal is a child of `body` (not `#centerPanel`), click events on its close buttons never bubble to the centerPanel listener. The `data-action="close-modal"` attributes are invisible.

## Pattern
Any modal, popup, or overlay that is appended directly to `document.body` (rather than inside `#centerPanel`) needs its own event handling. This applies to:
- `showAddLeadModal()` — Add Lead modal
- `editDealStage()` — Deal stage change modal
- `editDealValue()` — Deal value edit modal
- `showAttachDealModal()` — Attach deal modal

## Fix

Two patterns depending on how the modal is created:

**Pattern A — `createElement` + `appendChild`** (direct reference available):

```javascript
document.body.appendChild(modal);
modal.addEventListener('click', function(e) {
  var a = e.target.getAttribute && e.target.getAttribute('data-action');
  if (a === 'close-modal') {
    modal.remove();
  } else if (a === 'stop-propagation') {
    e.stopPropagation();
  }
});
```

**Pattern B — `insertAdjacentHTML`** (no direct reference):

```javascript
document.body.insertAdjacentHTML('beforeend', modalHtml);
var overlay = document.body.lastElementChild;
if (overlay && overlay.classList.contains('modal-overlay')) {
  overlay.addEventListener('click', function(e) {
    var a = e.target.getAttribute && e.target.getAttribute('data-action');
    if (a === 'close-modal') {
      overlay.remove();
    } else if (a === 'stop-propagation') {
      e.stopPropagation();
    }
  });
}
```

## Verification
1. Open modal (click "+ Add Lead")
2. Click ✕ button → modal closes
3. Open modal again, click "Cancel" button → modal closes
4. Open modal again, click the dark backdrop (outside the white box) → modal closes
5. Open modal again, click inside the white box → modal stays open (stop-propagation works)

## Pitfall: closing modals from other functions with fragile selectors

When `setDealStage()` (or any function that fires after a modal action) needs to close the modal, use the `.modal-overlay` class selector. **Do not use CSS attribute selectors on inline styles — they break when styling changes.**

```javascript
// RIGHT — uses .modal-overlay class
var modals = document.querySelectorAll('.modal-overlay');
for (var mi = 0; mi < modals.length; mi++) modals[mi].remove();

// WRONG — fragile CSS attribute selector breaks on style changes
var modal = document.querySelector('[style*="position:fixed"][style*="background:rgba"]');
if (modal) modal.remove();
```

The attribute selector was originally written to match modal overlays, but it fails silently when:
- Backdrop styling changes (e.g., `blur(4px)` instead of `blur(2px)`)
- The overlay uses CSS classes instead of inline styles
- Multiple modals stack (the selector only finds one)

## Real bug: `editDealStage()` and `editDealValue()` Cancel buttons not working

This exact bug was found in production. Both functions used `insertAdjacentHTML('beforeend', modalHtml)` without attaching a direct click listener. The Cancel button had `data-action="close-modal"` but no handler was listening for it.

**Fix applied:** Added Pattern B (above) to both functions — `document.body.lastElementChild` check + direct `click` listener on the overlay.

```javascript
function editDealStage(dealId) {
  ...
  document.body.insertAdjacentHTML('beforeend', modalHtml);
  var overlay = document.body.lastElementChild;
  if (overlay && overlay.classList.contains('modal-overlay')) {
    overlay.addEventListener('click', function(e) { ... });
  }
}
```

Also fixed `setDealStage()` to close the modal using `.modal-overlay` class instead of the fragile attribute selector.

## Related
- The `#centerPanel` delegation handles: deal cards, lead rows, navigation, filter pills, integration toggles, and action item buttons — all of which live inside `#centerPanel`
- The modal-local handler only needs `close-modal` and `stop-propagation` — all modal-internal CTA clicks (submit, upload, tab switch) pass through the `#centerPanel` delegation because those elements exist inside the modal's innerHTML which IS rendered within the context of `document.body`. Wait — actually no. Let me clarify:

**Correction**: Modal CTA buttons (like "Add Lead" submit, "Upload & Import", tab switches) are also inside the modal on `document.body`, so they ALSO won't reach `#centerPanel`. If you need those to trigger the delegation handler, the options are:
1. Add more actions to the modal-local listener
2. Use inline `onclick="functionName()"` for modal-internal CTAs (safe here because the attribute values don't contain single quotes)
3. Move the modal inside `#centerPanel` instead of `document.body`

For this session, option 2 was chosen for submit/upload buttons (they use inline onclick with no single quotes), and tab switches use `data-action="switch-lead-tab"` handled by the modal-local listener.
