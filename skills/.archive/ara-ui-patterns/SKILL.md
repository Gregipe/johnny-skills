---
name: ara-ui-patterns
description: Design conventions and UI patterns for the ARA dashboard — table layouts, color scheme, naming, modals, bulk operations. Apply these when building new pages or redesigning existing ones.
category: software-development
---

# ARA UI Patterns

Design conventions for the ARA dashboard at `localhost:8766`. Apply these when building new UI or refactoring existing pages. All CSS is inline in `server.py` (Python f-strings/HTMLResponse) or `_template.py` files.

## 🚫 HARD RULE: Never Change Existing UI When Building Features

When building new backend features or adding new data to the system, DO NOT touch the existing dashboard UI. This rule exists because of a corrective incident (June 17, 2026) where the Actions tab was converted from tables to card layouts during a data unification change, then had to be reverted — wasting effort and frustrating the user.

**The rule:**
- Backend delivers new data through existing API endpoints or new endpoints
- Frontend consumes data using its **existing rendering patterns** (table format, column layout, existing CSS classes)
- Never replace a table with cards, change column structure, alter styling, or touch `dashboard.js` rendering code unless explicitly asked
- If a new data type needs to be shown, reuse the existing patterns — don't invent new UI for it
- `dashboard_template.py` nav changes are the only permissible UI change (adding/removing nav items)

**Pitfall:** "I'm building a unified feed, so I should redesign the rendering" — NO. The data structure changes; the UI doesn't. Users value consistency over novelty.

**When features are discovered missing (regression):** Don't guess what was lost. Run the feature regression audit documented in `formal-release-cycle/references/feature-regression-audit.md`. The technique compares two backups by function definition diffing, keyword counting, dangling reference analysis, and escape corruption checks. The June 20 regression lost 8 functions (16KB) from dashboard.js — all passed `node -c` but left the dashboard with zero action editing mechanisms. The audit found every lost feature in under 5 minutes.

> **Note:** This skill supersedes `ara-frontend-patterns`.

**Prevention checklist before deploying a rewritten function:**
1. `git diff` or backup comparison: list every `id=` and `onclick=` that existed in the old version and verify each appears in the new version
2. List every event listener (`addEventListener`) and helper function called from the old modal — verify each is preserved or intentionally replaced
3. If a field changed from readonly+autofilled to editable, confirm the user asked for it
4. After deploy, do a visual smoke test: open the modal, verify all interactive elements work

> **Note:** This skill supersedes `ara-frontend-patterns`. The frontend patterns content has been merged into this skill as the authoritative reference for ARA UI development.

## Quick Reference: Frontend Patterns

If you came here looking for frontend-specific patterns, see these sections:

| Topic | Section |
|-------|---------|
| Table/Grid layouts | [Table-Grid Layout for Data Lists](#table-grid-layout-for-data-lists) |
| Checkbox patterns | [Checkbox on Rows](#checkbox-on-rows) |
| Bulk operations | [Bulk Operations](#bulk-operations) |
| B&W Dialog Modal | [B&W Dialog Modal (replace native confirm/alert)](#b-w-dialog-modal-replace-native-confirmalert) |
| Sidebar | [Sidebar Consistency](#sidebar-consistency) |
| Kanban Board | [Kanban Board (Deals Pipeline)](#kanban-board-deals-pipeline) |
| Chat Messages | [Chat Message Formatting](#chat-message-formatting) |
| Auto-Growing Textarea | [Auto-Growing Textarea in Flex Layout](#auto-growing-textarea-in-flex-layout) |
| Custom Radio/Chip inputs | [Custom Radio/Chip Input Styling](#custom-radiochip-input-styling) |

## Design Principle: Monochrome Only

ARA's visual language is **black, white, and grey only**. No color accents, no brand colors, no green/red/blue indicators. No emoji icons in UI elements — use plain text labels instead.

| Allowed | Not allowed |
|---------|-------------|
| `#111111` (black text, active backgrounds) | Colored accents (blue buttons, red badges) |
| `#FFFFFF` (white backgrounds) | Emoji icons in buttons, labels, section headers, or indicators |
| `#F5F5F7`, `#F8F8FA`, `#F0F0F2` (hover/locked states) | Status dots in color |
| `#E5E5E7`, `#EDEDEF` (borders) | Gradient backgrounds |
| `#6E6E73` (secondary text) | Colored pill backgrounds |
| `#9A9A9E`, `#BFBFC3`, `#D2D2D5` (muted) | - |

**Exceptions:** The ✎ edit/pencil and ✕ close button characters are monochrome text glyphs and are allowed. Colored emojis in user-generated data (lead names, conversation content, etc.) are preserved — only strip emoji from UI chrome.

**Toggle switches** use black (`#111`) for the "on" state, never green or blue.

**Cadence step timing labels** always include the word "times" after the repeat count: `Fire after 2h × 8 times × every 4h`. The "×" label is followed by "times" as a visible label next to the number input — not just implied by context.

**Before using an emoji in a label, button, section header, or indicator — use plain text instead.**

## Color Scheme

| Element | Value |
|---------|-------|
| Page background | `#FFFFFF` |
| Text | `#111111` |
| Secondary text | `#6E6E73` |
| Muted text | `#9A9A9E`, `#BFBFC3` |
| Borders | `#E5E5E7`, `#EDEDEF` |
| Hover backgrounds | `#F5F5F7`, `#F8F8FA`, `#F0F0F2` |
| Selected row | `#F2F2F5` with `inset 2px 0 0 #111` left border |
| Destructive actions | `#dc2626` bg, `#b91c1c` hover |

### Action / Primary Buttons

**Background:** `#111` (black), **text:** `#fff` (white). Icons inside buttons use `CSS filter` to render white on the dark background — never inline SVGs with `fill="#fff"` or separate icon elements. Apply the filter to the icon markup so it adapts automatically.

```css
filter: brightness(0) invert(1);  /* makes dark icons white on black bg */
```

## Table-Grid Layout for Data Lists

When rendering a list of items (threads, leads, deals, etc.), use a **CSS Grid** on each row, not flexbox slabs. This is sleeker and more scannable.

```css
.table{width:100%;border-collapse:collapse}
.table .tr{display:grid;grid-template-columns:36px 32px 1fr auto;align-items:center;padding:10px 12px;border-bottom:1px solid #EDEDEF;cursor:pointer;transition:all .1s;gap:8px}
.table .tr:hover{background:#F8F8FA}
.table .tr.selected{background:#F2F2F5;box-shadow:inset 2px 0 0 #111}
```

Grid columns from left to right:
1. **Checkbox** (`36px`) — hidden by default (opacity: 0), appears on row hover or when checked
2. **Index** (`32px`) — tabular-nums font, `#BFBFC3` color, right-aligned, user-select: none
3. **Body** (`1fr`) — title + subtitle preview stacked vertically
4. **Meta** (`auto`) — badges, counts, dates — fixed width, no wrapping

### Row Content Patterns

```javascript
// Column 1: Checkbox
'<div class="td-check" onclick="event.stopPropagation()">' +
  '<input type="checkbox" data-id="..." onchange="onCheckChange()">' +
'</div>' +
// Column 2: Index
'<div class="td-idx">' + (index + 1) + '</div>' +
// Column 3: Body
'<div class="td-body">' +
  '<div class="td-title">Title <span class="td-type badge">type</span></div>' +
  '<div class="td-preview">Subtitle or preview text</div>' +
'</div>' +
// Column 4: Meta
'<div class="td-meta">' +
  '<span class="td-pill">count</span>' +
  '<span>date</span>' +
'</div>'
```

### Type Badges

Small uppercase pills next to titles:
```css
.td-type{font-size:9px;padding:1px 6px;border-radius:4px;font-weight:600;text-transform:uppercase;letter-spacing:.3px;flex-shrink:0}
.td-type.general{background:#F0F0F2;color:#6E6E73}
.td-type.lead{background:#DBEAFE;color:#1E40AF}
.td-type.coaching{background:#FEF3C7;color:#92400E}
```

## Checkbox on Rows

- Hidden by default (`opacity: 0`), visible on hover OR when checked
- `accent-color: #111` to match theme
- Wrap in a div with `event.stopPropagation()` so clicking checkbox doesn't trigger row click

```css
.td-check input[type=checkbox]{width:15px;height:15px;cursor:pointer;accent-color:#111;border-radius:3px;opacity:0;transition:opacity .1s}
.tr:hover .td-check input[type=checkbox],
.td-check input[type=checkbox]:checked{opacity:1}
```

## Bulk Operations

When adding multi-select + bulk actions to a list page, follow the Threads page pattern:

1. **Select All checkbox** in toolbar — toggles all visible row checkboxes
2. **Delete button** — hidden by default, appears with count when selections exist ("Delete 3 threads")
3. **Confirmation modal** — "Are you sure?" dialog before destructive actions
4. **State reset** — after bulk delete, clear select-all state and reset the active item panel

### Delete Confirmation Modal

```html
<div class="modal-overlay" id="deleteModal">
  <div class="modal-box">
    <h3>Delete threads?</h3>
    <p id="deleteModalMsg">...</p>
    <div class="modal-actions">
      <button class="modal-cancel" onclick="closeModal()">Cancel</button>
      <button class="modal-confirm" onclick="executeDelete()">Delete</button>
    </div>
  </div>
</div>
```

Modal closes on overlay click (`e.target === this`) or Escape key.

### Modal CSS

```css
.modal-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.35);z-index:1000;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal-box{background:#fff;border-radius:16px;padding:28px 32px;max-width:420px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,.15)}
.modal-cancel{background:#F0F0F2;color:#111}
.modal-confirm{background:#dc2626;color:#fff}
```

## Naming

- Display **"Account"** instead of **"Company"** in labels and search results throughout the UI
- The database field stays `company` — no backend renames, only display-level changes

## Edit Action Modal (Pre-filled, PATCH, Read-only fields)

When adding an edit flow to an existing record (action item, deal, lead), follow this pattern:

### Modal structure
- **Title bar:** "Edit [Name]" + ✕ close button (top-right)
- **Body:** Pre-filled form fields from the existing record (fetched via GET)
- **Footer:** "Save Changes" (primary, black bg) + "Cancel" (secondary, grey bg)
- **Read-only fields:** Use `background:#F5F5F7` + `readonly` attribute for fields inherited from source-of-truth tables (e.g., lead name/email on a deal)

### Pre-fill pattern
```javascript
function editActionItem(actionId) {
  fetch('/api/actions/' + actionId)
    .then(function(r) { return r.json(); })
    .then(function(a) {
      var dueStr = a.due_at ? new Date(new Date(a.due_at).getTime() + 330*60*1000).toISOString().slice(0, 16) : '';  // UTC→IST correction for datetime-local
      // Build modal HTML with values pre-filled
      // Lead field is readonly (inherits from leads table)
      '<input id="editActionLead" disabled value="' + esc(a.lead_name) + '">'
      // Due date uses datetime-local input
      '<input type="datetime-local" id="editActionDue" value="' + dueStr + '">'
      // Select dropdowns pre-selected via "selected" attribute
      '<option value="whatsapp"' + (a.channel === 'whatsapp' ? ' selected' : '') + '>'
    });
}
```

### Save pattern (PATCH)
```javascript
function saveEditedAction(actionId) {
  var body = {
    title: document.getElementById('editActionTitle')?.value?.trim(),
    description: document.getElementById('editActionDesc')?.value?.trim(),
    owner: document.getElementById('editActionOwner')?.value,
    channel: document.getElementById('editActionChannel')?.value,
    due_at: dueVal ? new Date(dueVal).toISOString() : null,
  };
  fetch('/api/actions/' + actionId, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  }).then(function(r) {
    if (!r.ok) throw new Error('Failed');
    // Close modal, refresh the page/tab
    document.querySelector('.modal-overlay').remove();
    renderActionsPage();  // or loadActionsForLead(leadId)
  });
}
```

### Close behavior
- ✕ button → `this.closest('.modal-overlay').remove()`
- Cancel button → same
- Click outside modal (overlay background) → `onclick="if(event.target===this)this.remove()"`
- After successful save → auto-close + refresh

### Pitfalls
- **Don't use inline onclick for close** with deep nesting — use `this.closest('.modal-overlay').remove()` which works regardless of DOM depth
- **datetime-local values** must be in ISO format: `new Date(x).toISOString().slice(0, 16)` produces `YYYY-MM-DDTHH:MM`
- **Pre-fill select dropdowns** by adding `selected` attribute to the matching `<option>`, not by setting `.value` after innerHTML
- **Re-query after save** — if the edit modal was opened from a lead detail page, call `loadActionsForLead(leadId)` NOT `renderActionsPage()`, or the SPA routing replaces the lead page
- **REFACTORED LEAD-ID DETECTION (June 2026):** The old pattern `document.querySelector('[data-lead-id]')` is dangerously broad — on the Actions page (not lead detail), it can match lead checkbox rows and trigger a refresh on the wrong lead. The replacement pattern guards against this:
```javascript
// ❌ OLD — too broad, matches any data-lead-id on the page
var leadEl = document.querySelector('[data-lead-id]');
if (leadEl) loadActionsForLead(leadEl.getAttribute('data-lead-id'));

// ✅ NEW — scoped to the lead detail tab state
var leadTab = document.getElementById('leadActions');
if (leadTab && leadTab.style.display !== 'none') {
  loadActionsForLead(window._currentLeadId);
}
```
This uses `window._currentLeadId` (set when the lead detail view opens) and the `#leadActions` tab's visibility as a guard. The `deleteActionItem` backup code already uses this pattern — apply it to `saveEditedAction` and any future function that refreshes actions after edit/save/delete.
- **`action_` ID prefix mismatch (June 2026):** The `/api/activities` endpoint returns IDs like `action_493719ff` (with `action_` prefix), but `/api/actions/{id}` expects raw IDs (`493719ff`). The Actions page (Tasks tab) uses activities data, so `data-aid` gets the prefixed form. When Edit is clicked, it calls `/api/actions/action_493719ff` → **404**. Fix: use the canonical `_stripActionPrefix()` function in every function that calls `/api/actions/{id}`: `editActionItem()`, `saveEditedAction()`, `deleteActionItem()`, and `resolveActionItem()`. The function definition is:\n```javascript\nfunction _stripActionPrefix(id) {\n  return (typeof id === \"string\" && id.startsWith(\"action_\")) ? id.slice(7) : id;\n}\n```\nCall it at the top of each function: `actionId = _stripActionPrefix(actionId);` — then use the stripped ID in all subsequent `/api/actions/` calls. The old regex-based approach (`actionId.replace(/^action_/, '')`) works but drifts if a function forgets it; the named function makes the intent explicit and grep-able.
- **Inline modal positioning overrides flex centering (June 2026):** When a modal is created via `innerHTML` inside a `.modal-overlay` (which has `display:flex; align-items:center; justify-content:center`), do NOT use inline `margin:60px auto` on the inner modal box. The `align-items:center` from the flex parent already centers vertically — the `margin:60px` PUSHES the modal 60px below center, requiring the user to scroll up to see it. Use `margin:0 auto; max-height:85vh; overflow-y:auto` for the inner box so the flex parent handles all centering. Example fix:\n  ```javascript\n  // ❌ BROKEN — modal appears 60px below center, scrolled out of view\n  '<div style=\"background:#fff;...;margin:60px auto;position:relative\">'\n  // ✅ CORRECT — flex parent centers it\n  '<div style=\"background:#fff;...;margin:0 auto;max-height:85vh;overflow-y:auto;position:relative\">'\n  ```\n- **`.detail` vs `.error` in API error responses:** FastAPI 404s return `{"detail": "Action not found"}` — NOT `{"error": "..."}`. If the frontend checks `if (!a || a.error)`, the check silently passes (no `error` key) and the modal renders with `undefined` values for title/description/due date. Fix: check both: `if (!a || a.error || a.detail) { alert('Action not found'); return; }`

## Lead Inheritance on Deal Form

When selecting a lead in a deal/create form, auto-fill fields from the lead record. Lead is the source of truth — contact fields are read-only on the deal.

### Fields to inherit
| Lead field | Deal field | How |
|---|---|---|
| `name` | `contact_name` | Direct |
| `email` | `contact_email` | Direct, read-only |
| `phone` | `contact_phone` | Direct, read-only |
| `product_interest` | `contact_designation` | Direct |
| `company` | `org_name` | Auto-fill if blank |
| `segment` | `industry_segment` | Match dropdown by lowercase value |
| `lead_source` | `source_channel` | Match dropdown by lowercase value |

### Dropdown matching
```javascript
if (segment) {
  var indEl = document.getElementById('addDealIndustry');
  if (indEl) {
    for (var i = 0; i < indEl.options.length; i++) {
      if (indEl.options[i].value.toLowerCase() === segment.toLowerCase()) {
        indEl.value = indEl.options[i].value; break;
      }
    }
  }
}
```

### Rules
- Contact fields (name, email, phone, designation) are ALWAYS read-only on the deal — edit the lead to change them
- Company only auto-fills if org_name is currently blank (don't overwrite user input)
- Segment/source dropdowns match case-insensitively — the lead's `segment` value might differ from the deal form's `<option>` values

## SPA Hash Routing

ARA is a single-page app: all pages rendered client-side by `showPage(page)` in `dashboard.js`. To make refreshes, back/forward, and shareable URLs work, EVERY page navigation MUST update the URL hash via `history.replaceState()`:

```js
function showPage(page) {
  // nav highlighting...
  if (page === 'dashboard') {
    if (window.location.hash) history.replaceState(null, '', window.location.pathname);
  } else {
    var h = '#' + page;
    if (window.location.hash !== h) history.replaceState(null, '', h);
  }
  // render...
}
```

**Three parts needed:**
1. `showPage()` sets hash via `replaceState` (not `location.hash` — avoids triggering hashchange mid-function)
2. `hashchange` listener for back/forward: read hash → `showPage(hash)` or `showPage('dashboard')`
3. Initial load IIFE with interval polling: scripts may not be ready yet, poll every 50ms up to 5s

Known pages: `['leads','deals','activities','actions','knowledge','induction','integrations','threads','settings']`

### HTML Template Pitfalls

### Cross-Surface Migration

When moving a concept between per-template and global scope, use `references/cross-surface-migration.md` — it has the full checklist of surfaces to audit (static HTML, dynamic JS, cached data, server endpoints, migration logic). Map every surface before changing any of them.

### Kanban Board (Deals Pipeline)

The deals page uses a compact chip-based kanban with a right-side slide-in detail panel. See `references/kanban-board.md` for the full pattern — columns, chips, event delegation, and slide panel CSS/JS.

All 8 pipeline stages (NEW → DORMANT) must fit on one screen at 1280px using `flex:1` columns. Headers use `white-space: nowrap` + 9px font so the bottom border is at a uniform level regardless of name length.

View the reference for the full stage rail modal CSS, HTML, and JS patterns.

### Chat Message Formatting

Two separate code paths render chat messages (dashboard `addChatMsg` + threads `addMessage`). Both must use identical `\n→<br>` and `**bold**→<strong>` conversion. See `references/chat-message-formatting.md` for the exact code, CSS, and the lead profile initial message format.

### Lead Detail Tabs

The lead detail view has a tab bar (Timeline / Outreach Activity / Notes) with show/hide panels. See `references/lead-detail-tabs.md` for the tab switching function, scheduled actions rendering, and API contract (including the required `"Z"` UTC suffix on timestamps).

### Custom Radio/Chip Input Styling

When building custom-styled radio or checkbox chips (common for tone selectors, language pickers, etc.), hide the native `<input>` using `opacity:0; position:absolute` — **NOT** `display:none`.

```css
/* ❌ BROKEN — display:none prevents label click forwarding in some browsers */
.chip-group input { display:none; }

/* ✅ CORRECT — input is invisible but functional */
.chip-group input {
  opacity: 0;
  position: absolute;
  width: 0;
  height: 0;
  pointer-events: none;
}
```

**Why `display:none` breaks click forwarding:** When a `<label>` wraps an `<input type="radio">`, clicking the label should forward the click to the input (checking the radio). But if the input has `display:none`, some browsers treat the input as removed from the layout and don't forward label clicks. Using `opacity:0; position:absolute; width:0; height:0; pointer-events:none` visually hides the input while keeping it in the layout so label click forwarding works.

**Full chip pattern with selected state:**

```html
<div class="chip-group" id="pe_tone_chips">
  <label class="chip selected"><input type="radio" name="tone" value="calm" checked><span>Calm</span></label>
  <label class="chip"><input type="radio" name="tone" value="warm"><span>Warm</span></label>
  <label class="chip"><input type="radio" name="tone" value="persuasive"><span>Persuasive</span></label>
</div>
```

```css
.chip-group { display:flex; flex-wrap:wrap; gap:5px; }
.chip {
  display:inline-flex; align-items:center;
  padding:5px 10px; border:1px solid #E5E5E7; border-radius:20px;
  font-size:10px; color:#6E6E73; cursor:pointer;
  transition:all .12s; user-select:none; background:#fff;
}
.chip:hover { border-color:#C5C5C7; color:#111; }
.chip.selected { border-color:#111; color:#111; background:#F5F5F7; font-weight:500; }
.chip input { opacity:0; position:absolute; width:0; height:0; pointer-events:none; }
```

### JavaScript — updating selected class on click:

```javascript
// Delegated click handler on document
document.addEventListener('click', function(e) {
  var chipGroup = e.target.closest('.chip-group');
  if (chipGroup && e.target.closest('.chip')) {
    chipGroup.querySelectorAll('.chip').forEach(function(c) { c.classList.remove('selected'); });
    e.target.closest('.chip').classList.add('selected');
  }
});
```

**When programmatically selecting a chip (e.g., from prefill data):**

```javascript
// Set the radio AND update the CSS class
var radio = container.querySelector('.chip-group input[value="' + tone + '"]');
if (radio) {
  radio.checked = true;
  container.querySelectorAll('.chip-group .chip').forEach(function(c) {
    c.classList.toggle('selected', c.contains(radio));
  });
}
```

## JavaScript onclick Escaping in innerHTML (Critical Pitfall)

When generating HTML with inline `onclick` handlers via JavaScript string concatenation and `innerHTML`, **never use `\'` or `\\'` to pass variable values**. Both fail silently or produce broken JavaScript. Two safe alternatives:

### ❌ Broken patterns

```javascript
// BROKEN: \\' becomes literal backslash+quote, breaking the outer JS string
container.innerHTML = '...onclick="func(\\'' + var + '\\'  )"...';

// BROKEN: even if it renders, browsers don't execute <script> tags in innerHTML
container.innerHTML = '...<script>doThing();</script>';
```

The `\'` escape works inside JS string literals, but when these strings become HTML attributes, the browser parses them as:
1. Outer JS string → produces HTML with `onclick="func(\' + var + \')"`
2. HTML parser → the `\'` becomes a literal backslash + apostrophe in the attribute
3. On click, the handler expression is syntactically broken

### ✅ Safe pattern: data- attributes with event delegation (RECOMMENDED)

```javascript
// Pattern A: data-idx + _leadsData (best for dynamic lists)
drop._leadsData = leads;
drop.innerHTML = leads.map(function(l, i) {
  return '<div data-idx="' + i + '" style="cursor:pointer">' +
    esc(l.name) + '</div>';
}).join('');

drop.addEventListener('click', function(e) {
  var el = e.target.closest('[data-idx]');
  if (!el || !drop._leadsData) return;
  var lead = drop._leadsData[parseInt(el.getAttribute('data-idx'))];
  if (lead) onSelect(lead);
  drop.style.display = 'none';
});
```

```javascript
// Pattern B: named data- attributes (best for multi-field records)
drop.innerHTML = leads.map(function(l) {
  return '<div data-lid="' + l.id + '" data-lname="' + esc(l.name) +
    '" data-lemail="' + esc(l.email||'') + '" style="cursor:pointer">' +
    esc(l.name) + '</div>';
}).join('');

drop.addEventListener('click', function(e) {
  var el = e.target.closest('[data-lid]');
  if (!el) return;
  var id = el.getAttribute('data-lid');
  var name = el.getAttribute('data-lname');
  var email = el.getAttribute('data-lemail');
  onSelect(id, name, email);
  drop.style.display = 'none';
});
```

The `data-` attribute value passes through string concatenation cleanly. Event delegation via `addEventListener('click', ...)` with `closest('[data-attr]')` avoids all quote escaping — no inline `onclick` needed.

**CRITICAL PITFALL — selector must match attributes:** The HTML uses `data-lid`/`data-lname`/`data-lemail` but the click handler queries `closest('[data-idx]')`. These don't match — `closest` always returns `null`, every click is silently ignored. **Verify the selector string matches exactly one of the data- attribute names in the HTML.**

**CRITICAL PITFALL — IIFE scope + inline onclick = silent failure (June 2026):** `dashboard.js` is wrapped in `(function() { ... })()` — an IIFE. Every function defined inside (`editActionItem`, `resolveActionItem`, `deleteActionItem`) is **private** to that scope. Inline `onclick="editActionItem('...')"` in HTML searches for those names in the **global** scope — they are not there. The browser silently swallows the error (no console warning, no crash). The button renders but clicking does nothing. **The class-based event delegation pattern (`.am-toggle`, `.am-edit`, etc.) works because `document.addEventListener("click", ...)` is registered INSIDE the IIFE where those functions live.** Every action menu in ARA must use class-based event delegation, never inline onclick.

**CRITICAL PITFALL — new action class requires delegation handler (June 2026):** When adding a new action type to the class-based dropdown menu (e.g., `.am-delete` for trash), you MUST add a corresponding `closest(".am-delete")` handler in the `document.addEventListener("click", ...)` delegation block at the top of `dashboard.js`. The HTML will render, the class will be there, but clicks will be silently swallowed if no handler matches. The three handlers that MUST exist for any new class: (1) toggle handler for `.am-toggle` to open/close the dropdown, (2) action handler for the specific class (`.am-edit`, `.am-done`, `.am-delete`), (3) outside-click handler to close all `.am-dropdown` menus. Verify: `grep -n "am-delete\|am-edit\|am-done" /opt/ara/static/dashboard.js` — each class must appear BOTH in the HTML template strings AND in the document-level click handler.

**CRITICAL PITFALL — `a.id` inside onclick string (June 15, 2026):** When generating inline onclick handlers via string concatenation, a loop variable like `a.id` appears inside the onclick attribute string. Even when the string concatenation is correct, `a` is undefined in the onclick scope:

```javascript
// ❌ BROKEN — a.id is a JS variable in onclick scope, but a is undefined
var editMenu = '<button onclick="editActionItem(\\'' + a.id + '\\')">';
// The escaped quotes make the HTML: onclick="editActionItem(\'' + a.id + '\')"
// a is undefined when the click fires → a.id throws ReferenceError
```

The fix is event delegation with data attributes:
```javascript
// ✅ CORRECT — no escaping, no scope issues
var editMenu = '<span class="am-container">' +
  '<button class="am-toggle">⋮</button>' +
  '<div class="am-dropdown">' +
    '<div class="am-edit" data-aid="' + a.id + '">✏️ Edit</div>' +
  '</div></span>';

// Single document-level listener
document.addEventListener("click", function(e) {
  var edit = e.target.closest(".am-edit");
  if (edit) { editActionItem(edit.getAttribute("data-aid")); return; }
  var toggle = e.target.closest(".am-toggle");
  if (toggle) { /* show/hide dropdown */ return; }
  // Close all on outside click
});
```

**Note:** The `data-aid` attribute value is set via direct string concatenation (`' + a.id + '`), not inline onclick. The JS event listener reads it with `getAttribute()`. Zero escaping, zero scope issues.

### ✅ Safe pattern: direct function call after innerHTML

```javascript
// For <script>-equivalent behavior, call the function directly after setting innerHTML
container.innerHTML = '...loading...';
loadActionsForLead(leadId);  // runs immediately after DOM update
```

Browsers refuse to execute `<script>` tags injected via `innerHTML` as a security measure. The workaround is to call the function directly after the innerHTML assignment — this is equivalent and always works.

### Other safe patterns in the codebase

The existing dashboard code uses `&#39;` (HTML entity for apostrophe) and `\\'` in patterns like:
```javascript
'<div onclick="func(&#39;' + var + '&#39;)"...>'   // Pre-existing pattern — fragile but functional
```

These work in the existing codebase due to specific escaping chains but are fragile. **For new code, prefer data- attributes or direct function calls.**

### When the dashboard breaks silently after a JS file change

1. Run `node --check /opt/ara/static/dashboard.js` before deploying
2. If it passes but the page is blank, check the browser console for `SyntaxError: Invalid or unexpected token`
3. The error will point at the first line where the JS parser fails — scroll to that line and look for broken `onclick` handlers with escaped quotes
4. For server.py code insertions over SSH, prefer `sed -i "LINE r file"` over Python heredocs — see `references/ssh-code-insertion.md`

## Three-Dot Action Menu (⋮ + Popup)

Every action row in a table gets a `⋮` button that opens a popup menu with Edit, Mark as Done, and Delete options. This replaces inline ✏️✕ buttons — cleaner and scales to more options.

### Pattern (class-based event delegation)

The `am-*` convention documented under "JavaScript onclick Escaping" is the canonical implementation. Summary:

```html
<!-- In each row -->
<span class="am-container">
  <button class="am-toggle">⋮</button>
  <div class="am-dropdown">
    <div class="am-edit" data-aid="{id}">✏️ Edit</div>
    <div class="am-done" data-aid="{id}">✓ Mark as Done</div>
    <div class="am-delete" data-aid="{id}">✕ Delete</div>
  </div>
</span>
```

```javascript
// Single document-level delegation handler
document.addEventListener("click", function(e) {
  var toggle = e.target.closest(".am-toggle");
  if (toggle) { /* toggle dropdown visibility */ return; }
  var edit = e.target.closest(".am-edit");
  if (edit) { editActionItem(edit.getAttribute("data-aid")); return; }
  var done = e.target.closest(".am-done");
  if (done) { markActionDone(done.getAttribute("data-aid")); return; }
  var del = e.target.closest(".am-delete");
  if (del) { deleteActionItem(del.getAttribute("data-aid")); return; }
  // Close all am-dropdowns on outside click
  document.querySelectorAll(".am-dropdown").forEach(function(d) { d.style.display = "none"; });
});
```

### Three rules for new action classes

1. **HTML template** must include the class (`.am-edit`, `.am-done`, `.am-delete`)
2. **Delegation handler** must have a matching `closest(".am-XXX")` branch
3. **Outside-click closer** must close all `.am-dropdown` menus

Missing any of these = silently broken buttons. Verify with: `grep -n "am-edit\|am-done\|am-delete" /opt/ara/static/dashboard.js` — each class must appear BOTH in HTML templates AND in the click handler.

**CRITICAL PITFALL — function name collision with existing code (June 2026):** When adding new global functions to dashboard.js, check for name collisions with existing functions. `dashboard.js` has 5000+ lines and multiple code paths (Actions page, Lead detail tab, Deals page) that may define functions with the same name but different signatures. Example: adding `function markSelectedDone()` for bulk ops collided with the existing `async function markSelectedDone(leadId)` in the Lead detail tab. JavaScript silently uses the last-defined version, breaking the earlier caller. Before adding any new function: `grep -n "function FUNCTION_NAME" /opt/ara/static/dashboard.js`. If it already exists, use a different name (prefer `_` prefix for internal helpers: `_markBulkDone`).

### Popup text styling (BLACK TEXT ONLY)

Popup menu items use **black text (`color: #111`)** with colorful icons only. Never use colored text in popup items — no green for "Mark as Done", no red for "Delete". The icon (emoji/glyph) provides the visual cue; the text stays monochrome.

```css
/* ✅ CORRECT — black text, icon carries the color */
.am-edit { color: #111; }    /* ✏️ icon is the visual cue */
.am-done { color: #111; }    /* ✓ icon is the visual cue */
.am-delete { color: #111; }  /* ✕ icon is the visual cue */

/* ❌ WRONG — colored text is too vivid */
.am-done { color: #34c759; }   /* green text — too loud */
.am-delete { color: #dc2626; }  /* red text — too loud */
```

Hover states use `background: #f2f2f7` (subtle grey), never colored backgrounds.

### Popup positioning

The dropdown is positioned with `position: absolute; right: 0; top: 100%; z-index: 100` relative to `.am-container` (which is `position: relative`). This floats the popup outside the row without layout shifts.

### Function name collision with existing dashboard.js globals

`dashboard.js` is a single IIFE scope — all functions share the same namespace. Before adding a new global function, **grep the file for the proposed name** to ensure it doesn't collide with an existing function in a different section (e.g., a lead-detail-tab function with the same name but different signature).

```bash
grep -n "function markSelectedDone" /opt/ara/static/dashboard.js
```

**Pitfall (June 2026):** `markSelectedDone()` was added as a bulk-operation function on the Actions page. But `markSelectedDone(leadId)` already existed in the Lead detail tab. In JS, the later definition wins — the lead-detail-tab calls broke silently because the no-arg version replaced the parameterized one. **Fix:** rename the new function to avoid collision (e.g., `_markBulkDone()`).

### Scoping rule: mockup first, then build

When Greg asks for a UI redesign (menus, buttons, layouts), build a **standalone HTML mockup** first — show, don't tell. Open it in the browser so he can approve the visual direction before any code touches the dashboard. The mockup should use the ARA design conventions (monochrome, 11-12px fonts, compact) but can be simplified JS (inline handlers in a standalone file are fine; the real implementation uses `am-*` delegation). Only after visual approval do you implement against the real codebase with the proper event delegation patterns.

## B&W Dialog Modal (replace native confirm/alert)

All alerts and confirmations across the platform use a custom monochrome `<dialog>` element instead of the browser-native `confirm()` and `alert()`. This is consistent with the black-and-white aesthetic.

### Architecture

A single `<dialog id="bwDialog">` element is appended to `<body>` at page load. It's created by whichever JS file fires first (dashboard.js on the dashboard page, prompt_builder_template's inline script on the cadence page — both check if `bwDialog` already exists before creating).

The dialog is styled inline via JS with the monochrome palette:
- White card (`#fff`), dark text (`#111`), secondary text (`#555`)
- 12px border-radius, max 400px wide, 90vw max
- Shadow: `0 8px 32px rgba(0,0,0,0.12)`
- Backdrop: `rgba(0,0,0,0.4)` via `::backdrop` CSS pseudo-element
- Border separator: `1px solid #e5e5e7`

### API

| Function | Signature | Returns | Use |
|----------|-----------|---------|-----|
| `bwAlert(msg)` | `(msg: string) => void` | Nothing | One-button OK dialog for info/error messages |
| `bwConfirm(msg)` | `(msg: string) => Promise<boolean>` | Resolves `true/false` | Two-button Cancel/OK dialog for confirmations |

### Implementation

```javascript
(function() {
  if (document.getElementById('bwDialog')) return; // avoid duplicate

  // Backdrop style
  var s = document.createElement('style');
  s.textContent = '#bwDialog::backdrop { background:rgba(0,0,0,0.4); }';
  document.head.appendChild(s);

  var d = document.createElement('dialog');
  d.id = 'bwDialog';
  d.style.cssText = 'border:none;border-radius:12px;padding:0;max-width:400px;width:90vw;background:#fff;box-shadow:0 8px 32px rgba(0,0,0,0.12),0 2px 8px rgba(0,0,0,0.06);font-family:-apple-system,BlinkMacSystemFont,sans-serif;margin:auto;position:fixed;inset:0;';
  d.innerHTML = '<div style="padding:24px 28px 16px;"><div id="bwDTitle" style="font-size:15px;font-weight:600;color:#111;margin-bottom:8px;"></div><div id="bwDMsg" style="font-size:13px;color:#555;line-height:1.5;"></div></div><div id="bwDActions" style="display:flex;justify-content:flex-end;gap:6px;padding:12px 28px;border-top:1px solid #e5e5e7;"></div>';
  document.body.appendChild(d);

  var resolveConfirm = null;

  window.bwAlert = function(msg) {
    document.getElementById('bwDTitle').textContent = '';
    document.getElementById('bwDMsg').textContent = msg;
    document.getElementById('bwDActions').innerHTML =
      '<button onclick="document.getElementById(\'bwDialog\').close()" style="background:#111;color:#fff;border:none;padding:6px 18px;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;">OK</button>';
    d.showModal();
  };

  window.bwConfirm = function(msg) {
    return new Promise(function(resolve) {
      resolveConfirm = resolve;
      document.getElementById('bwDTitle').textContent = 'Confirm';
      document.getElementById('bwDMsg').textContent = msg;
      document.getElementById('bwDActions').innerHTML =
        '<button onclick="window._bwCancel()" style="background:transparent;color:#555;border:1px solid #e5e5e7;padding:6px 18px;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;">Cancel</button>' +
        '<button onclick="window._bwConfirm()" style="background:#111;color:#fff;border:none;padding:6px 18px;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;">OK</button>';
      d.showModal();
    });
  };

  window._bwConfirm = function() { d.close(); if (resolveConfirm) { resolveConfirm(true); resolveConfirm = null; } };
  window._bwCancel = function() { d.close(); if (resolveConfirm) { resolveConfirm(false); resolveConfirm = null; } };
})();
```

### Pitfalls

- **bwConfirm returns a Promise** — unlike native `confirm()` which is synchronous. Code that calls `bwConfirm()` must use `.then()` or `await`. The old pattern `if (!confirm(...)) return;` changes to `bwConfirm(...).then(function(ok) { if (ok) doSomething(); });`
- **Dialog centering requires explicit CSS** — native `<dialog>` with `showModal()` doesn't center properly when inline styles are set via `style.cssText`. The `margin:auto` alone is insufficient; you MUST also set `position:fixed;inset:0` for reliable centering in all browsers.
- **Dual injection** — `dashboard.js` creates it for SPA pages, `prompt_builder_template.py` creates it for the cadence page. The `if (document.getElementById('bwDialog')) return` guard prevents duplicates.
- **Global window.confirm/alert override** — `dashboard.js` overrides `window.confirm` and `window.alert` to use `bwAlert()`. This means all existing `confirm()`/`alert()` calls in dashboard.js render the B&W dialog. The override is NOT in the cadence page's inline script (to avoid conflicts).
- **CRITICAL: Cadence page doesn't load dashboard.js.** The `/cadence` page is served from `cadence_template.py` — it has its own `<script>` in `prompt_builder_template.py` but does NOT include `<script src="/static/dashboard.js">`. Any JS functionality that needs to work on BOTH pages (dashboard + cadence) must be inlined in `prompt_builder_template.py` OR added to dashboard.js AND duplicated/loaded on the cadence page separately.

## Unsaved Changes Warning (Dirty Flag Pattern)

When a user has unsaved changes in the Prompt Builder and tries to close/navigate away, a B&W confirm dialog warns them. This uses a `window.pbDirty` flag pattern.

### How It Works

1. **Flag tracking** — two delegated event listeners mark `window.pbDirty = true` on any `input` or `change` event inside `#pbOverlay`
2. **Flag reset** — set to `false` on open (`openPromptBuilder`) and on successful save (`savePromptBuilder`)
3. **Close guard** — `closePromptBuilder()` checks `pbDirty` before closing. If dirty, shows `bwConfirm()` — only closes on confirm
4. **Page-nav guard** — `beforeunload` handler checks `pbDirty` and triggers the browser's native leave warning

### Implementation

```javascript
// Track — mark dirty on any input/change in the builder
document.addEventListener('input', function(e) {
  if (e.target.closest('#pbOverlay')) window.pbDirty = true;
});
document.addEventListener('change', function(e) {
  if (e.target.closest('#pbOverlay')) window.pbDirty = true;
});

// Close guard
function closePromptBuilder() {
  if (window.pbDirty) {
    window.bwConfirm('You have unsaved changes. Are you sure you want to close?')
      .then(function(ok) {
        if (ok) _doClosePb();
      });
  } else {
    _doClosePb();
  }
}

// Page-nav guard
window.addEventListener('beforeunload', function(e) {
  if (window.pbDirty) {
    e.preventDefault();
    e.returnValue = '';
  }
});
```

### Pitfalls

- **bwConfirm is async** — the close function needs restructuring from `if (!confirm(...)) return` to a `.then()` callback. The overlay doesn't close until the user confirms. Keep the "close body" in a separate function (`_doClosePb`) so both paths (clean close + confirmed close) can call it.
- **beforeunload requires `e.preventDefault()` AND `e.returnValue = ''`** — modern browsers require both for the dialog to appear.
- **Reset on every open** — `window.pbDirty = false` must be set at the top of `openPromptBuilder()` so a fresh open starts clean even if stale data is in the DOM.
- **Save resets** — both `savePromptBuilder()` branches (with and without validation) must set `window.pbDirty = false` after successful save.

### HTML Comment Syntax in Python Raw Strings

ARA templates are Python raw strings (`r"""..."""`) containing HTML. Standard HTML comments use `<!-- -->`. **Never deviate from `-->` as the closing delimiter** — replacing `-->` with a Unicode arrow `→` silently swallows everything after the comment, breaking the page with zero errors in the browser console (the HTML parser treats it as a valid, unclosed comment).

```python
# ✅ CORRECT
r"""...<!-- ── Thread list ── --><div class="center">...

# ❌ BROKEN — Unicode → replaces -->
<!-- ── Thread list ── →<div class="center">...   ← page blank
```

**Detection:** Page returns HTTP 200 but `document.getElementById('any-element')` returns null for elements in the center/body section. Inspect the raw HTML for an unclosed `<!--` with a non-standard ending.

**Fix:** Restore exact `-->` via patch. Verify with `document.getElementById('threadCount') !== null` after fix.

### Separate Template Files

Some UI pages use a dedicated `_template.py` file (e.g., `threads_template.py`) instead of inline strings in `server.py`:
- `THREADS_HTML = r"""..."""` — raw string constant
- `get_threads_html(tenant_id)` — does `THREADS_HTML.replace("{{TENANT_ID}}", tenant_id)`

The `{{...}}` placeholder syntax is chosen specifically to avoid Python f-string brace conflicts. Raw strings mean `\n` is literal — cannot end a line with backslash.

### Bulk Delete Route Ordering

A literal-path route (e.g., `POST /api/threads/bulk-delete`) MUST be defined BEFORE a parameterized route (`POST /api/threads/{tenant_id}`) for the same HTTP method. FastAPI matches first-come — `{tenant_id}` matches the string `"bulk-delete"` as a valid ID, so the specific literal route is never hit if defined second. Physically move the function definition above the parameterized one.

## Cadence Prompt Builder

The `/cadence` page opens a **full-screen slide-over** (not a modal) when the user
clicks "✎ Open Builder". Three columns: sidebar | main workspace | live stats.
See `references/cadence-prompt-builder.md` for the full data model, all 8 tabs,
CSS classes, JS functions, prefill endpoint, and pitfalls.
See `references/prompt-builder-save-flow.md` for the save/publish flow, unsaved changes warning, and cross-surface checklist for adding new fields.
See `references/shareable-decks-per-stage.md` for the per-stage deck assignment UI (toggles + pin buttons) in the Conversational Playbook's Engaged/Meeting Requested/Scheduled/Completed/Closed stages.

### Key Architecture (current as of May 2026)

**Global Template Model:** The Outreach Central page has three layers:
1. **Global (top):** Outreach Template + Conversational Playbook — configured once, inherited by all cadences
2. **Per-template (middle):** Template cards ([Outbound] [Inbound] [Nurture]) + Objective tile (editable via `editObjective()` with `prompt()`)
3. **Per-template (bottom):** Cadence steps (channels × timing × repeats) + Reachout/Stop Conditions

Page layout order: Mapping strip → Outreach Template (global) → Playbook (global) → Template cards → Objective → Cadence + Conditions.

**Slide-over** replaces the old modal: `transform: translateX(100%) → 0` with
  `backdrop-filter: blur(4px)`. 92vw wide, max 1440px.
- **Separate template file** (`prompt_builder_template.py`) exports `PROMPT_BUILDER_HTML`
  raw string. Appended to `CADENCE_HTML` via string concatenation.
- **6 architecture bar steps** (no Objective — moved to per-template): Brand→Sector→Security→WhatsApp→Email→Call→Final Prompt (1→2→3→4→5→6→F).
- **Tabs**: Brand & Personality, Sector Intelligence, Security & Guardrails, WhatsApp, Email,
  Voice Call, Final System Prompt (7 tabs — no Objective tab).
- **Live stats** on Final tab: token counter, context bar, module breakdown, validation.
- **Prefill auto-fetches** from `/api/cadence/prefill` when `globalPromptParts` are empty.
  Splits response: objective goes to `t.objective`, rest to `globalPromptParts`.
  Uses real induction DB data (pain points, competition, pricing, restricted claims).
- **Tone mapping in prefill**: funny→persuasive, warm→warm, formal→formal, casual→friendly.
- **CSS prefix**: `pb-*` for all prompt builder styles (.pb-overlay, .pb-arch-bar, etc.)
- **Sysprompt assembly:** `assembleSystemPrompt(t)` merges `globalPromptParts` (brand, sector, security, channels) with `t.objective` (per-template). The validate endpoint receives only global promptParts — objective is appended at runtime.

## Sidebar Consistency

Every page in ARA must use the **identical sidebar**. If you modify the sidebar on one page, audit ALL pages that have a sidebar (dashboard, threads, cadence) and propagate the change. Inconsistency between pages is a common visual bug.

### Canonical Sidebar HTML — SVG Icons

Use SVG icons (not emojis) for a clean, styled appearance. Icons use `stroke="currentColor"` with `stroke-width="2"` so they inherit nav-item color and hover states.

```html
<div class="sidebar">
  <div class="sidebar-header">
    <div class="sidebar-logo">AR</div>
    <div class="sidebar-title">Autonomous<br>Revenue Agent <span>v1.0</span></div>
  </div>
  <div class="sidebar-nav">
    <div class="nav-section">
      <div class="nav-section-title">Main</div>
      <div class="nav-item" onclick="window.location='/'"><span class="icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9,22 9,12 15,12 15,22"/></svg></span> Home</div>
      <div class="nav-item" onclick="window.location='/leads'"><span class="icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></span> Leads</div>
      <div class="nav-item" onclick="showDeals()"><span class="icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg></span> Deals</div>
      <div class="nav-item" onclick="showPage('actions')"><span class="icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg></span> Actions</div>
    </div>
    <div class="nav-section">
      <div class="nav-section-title">Intelligence</div>
      <div class="nav-item" onclick="window.location='/#actions'"><span class="icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg></span> Actions</div>
      <div class="nav-item" onclick="window.location='/cadence'"><span class="icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10,9 9,9 8,9"/></svg></span> Outreach Central</div>
    </div>
    <div class="nav-section">
      <div class="nav-section-title">Learning</div>
      <div class="nav-item" onclick="window.location='/#knowledge'"><span class="icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg></span> Knowledge Base</div>
      <div class="nav-item" onclick="window.location='/#induction'"><span class="icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22,4 12,14.01 9,11.01"/></svg></span> Induction</div>
      <div class="nav-item" onclick="window.location='/#learnings'"><span class="icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg></span> Learnings</div>
    </div>
    <div class="nav-section">
      <div class="nav-section-title">Configuration</div>
      <div class="nav-item" onclick="showIntegrations()"><span class="icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg></span> Integrations</div>
      <div class="nav-item" onclick="window.location='/threads'"><span class="icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg></span> Threads</div>
    </div>
  </div>
  <div class="sidebar-footer">
    <div class="sidebar-user">
      <div class="avatar">G</div>
      <div class="info"><div class="name">Greg</div><div class="role">Business Lead · Hunar.ai</div></div>
    </div>
  </div>
</div>
```

### SVG Over Dropdown Icons for showDeals / showIntegrations

When a nav item uses a JavaScript function instead of a direct URL (e.g., `showDeals()`, `showIntegrations()`), the sidebar must define a stub `showDeals`/`showIntegrations` function that navigates to the correct page. On standalone pages (threads, cadence), these stubs navigate via `window.location` rather than SPA routing:

```javascript
function showDeals() { window.location.href = '/'; }
function showIntegrations() { window.location.href = '/dashboard#integrations'; }
```

### When to Sync Sidebar Across Pages

Modifying the sidebar on ONE page REQUIRES propagating the change to all pages:
- `dashboard_template.py`
- `cadence_template.py`
- `threads_template.py`

Check each file for duplicate sidebar HTML. All standalone pages have their OWN sidebar HTML that must match exactly (except the `active` class on the current page's item).

### Sections

| Section | Items |
|---------|-------|
| **Main** | Home, Leads, Deals, Actions |
| **Intelligence** | Outreach Central |
| **Learning** | Knowledge Base, Induction, Learnings |
| **Configuration** | Integrations, Threads, Settings |

### Active state

Set `class="nav-item active"` on the current page's item. Only one active at a time. The active state uses `background: #E0E0E5; font-weight: 600`.

### CSS

```css
.nav-section{margin-bottom:8px}
.nav-section-title{padding:6px 10px 4px;font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.6px;color:#9A9A9E}
.sidebar-footer{padding:12px 8px;border-top:1px solid #E5E5E7}
.sidebar-user{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;cursor:pointer}
.sidebar-user:hover{background:#E8E8ED}
.sidebar-user .avatar{width:28px;height:28px;border-radius:50%;background:#D0D0D5;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;color:#6E6E73}
.sidebar-user .info .name{font-size:13px;font-weight:600;color:#111}
.sidebar-user .info .role{font-size:11px;color:#6E6E73}
```

### Stub Functions

Pages with a standalone sidebar (threads, cadence) need their own stub functions for sidebar nav actions:

```javascript
function showDealsPage() { window.location.href = '/'; }
function showIntegrations() { window.location.href = '/dashboard#integrations'; }
```

These are separate from the SPA `showPage()` function used by the dashboard. Standalone pages navigate via `window.location` rather than SPA routing.

### Footer Difference — Dashboard vs Prompt Builder

The main ARA dashboard sidebar footer shows `avatar + name + role`:
```html
<div class="sidebar-user">
  <div class="avatar">G</div>
  <div class="info"><div class="name">Greg</div><div class="role">Business Lead · Hunar.ai</div></div>
</div>
```

The Prompt Builder sidebar (`prompt_builder_template.py`) shows `avatar + name only`:
```html
<div class="pb-sidebar-footer">
  <div class="pb-user-avatar">G</div>
  <span class="pb-user-name">Greg</span>
</div>
```

The user explicitly removed the role text — maintain this difference when updating either sidebar. **When you modify one sidebar footer, audit the other.** The prompt builder uses the `pb-` CSS prefix; the dashboard sidebar uses no prefix for footer elements.

### Cache-Busting

When modifying static JS files (`static/dashboard.js`), bump the version parameter in the `<script>` tag:

```html
<script src="/static/dashboard.js?v=N"></script>
```

Increment `v=N` with each change. Browsers aggressively cache static files served by FastAPI's `StaticFiles` mount — without a version bump, the fix won't take effect until the user does a hard refresh with DevTools open.

## Auto-Growing Textarea in Flex Layout

The ARA dashboard chat input uses an auto-growing `<textarea>` inside a `display: flex; align-items: center` container. See `references/auto-growing-textarea.md` for the full pattern — HTML, CSS, JS, and pitfalls (flex height conflicts, Enter-vs-Shift+Enter, cache-busting).

Key rules for this pattern:
- **HTML:** `<textarea rows="1">` with `oninput="autoGrowChatInput(this)"`, Enter submits via `onkeydown`, Shift+Enter inserts newline
- **CSS:** `align-self: flex-start` — critical to prevent flex from overriding the JS-controlled height
- **JS:** `el.style.height = '0px'` (not `'auto'`) forces proper reflow before reading `scrollHeight`

Apply this pattern to any text input in a flex layout that needs to expand vertically.

## Stage Filter Pills (Leads Table)

The leads table uses a **filter pill bar** above the table to allow quick sorting by stage. Each pill shows the stage name + count, and clicking filters both client-side and via `?stage=` API param.

### Filter Pills

```html
<div class="leads-stage-filter">
  <span class="sf-pill active" onclick="filterLeadsByStage('all')">All (15)</span>
  <span class="sf-pill" onclick="filterLeadsByStage('new')">New (3)</span>
  <span class="sf-pill" onclick="filterLeadsByStage('reached_out')">Reached Out (5)</span>
</div>
```

```css
.leads-stage-filter { display:flex; gap:6px; margin-bottom:12px; flex-wrap:wrap; }
.sf-pill { font-size:11px; font-weight:500; padding:4px 12px; border-radius:14px;
           border:1px solid #E5E5E7; background:#fff; cursor:pointer; color:#6E6E73;
           transition:all 0.15s; white-space:nowrap; }
.sf-pill:hover { border-color:#bbb; color:#111; }
.sf-pill.active { background:#111; border-color:#111; color:#fff; }
```

### Stage Badges (per row)

Each lead row shows a color-coded stage badge. Colors are semantic — not decorative:

```css
.stage-badge { font-size:10px; font-weight:500; padding:2px 8px; border-radius:10px;
               display:inline-block; white-space:nowrap; }
.stage-badge.new { background:#E8EAF6; color:#283593; }
.stage-badge.reached_out { background:#FFF3E0; color:#E65100; }
.stage-badge.engaged { background:#E3F2FD; color:#1565C0; }
.stage-badge.qualified { background:#E8F5E9; color:#2E7D32; }
.stage-badge.meeting_booked { background:#F3E5F5; color:#7B1FA2; }
.stage-badge.dormant { background:#F5F5F5; color:#9E9E9E; }
.stage-badge.lost, .stage-badge.closed_lost { background:#FFEBEE; color:#C62828; }
.stage-badge.closed_won { background:#E8F5E9; color:#1B5E20; }
```

### Stage column in leads table

The Stage column sits **between Account and Source** — not at the end:

```html
<th>Name</th><th>Account</th><th>Stage</th><th>Source</th><th>Owner</th>
```

### Filter logic

1. All leads loaded from API, counts computed by iterating `l.stage || 'new'` in JS
2. `window._stageFilter` tracks current filter (default `'all'`)
3. API call appends `?stage=` param for server-side filtering at scale
4. Full dataset is stored in `window._allLeads` so counts stay accurate even when filtered
5. `filterLeadsByStage(stage)` sets `window._stageFilter` and re-renders

```javascript
function filterLeadsByStage(stage) {
  window._stageFilter = stage;
  renderLeads();
}
```

### When to use

- Any data table where records have a categorical status that the user needs to sort by
- Always compute counts from the full dataset (not filtered), so pills show accurate totals
- Use semantic colors for stage/badge differentiation, not just monochrome — this is one of the few places ARA uses color

### Pitfalls

- **Don't filter only client-side at scale** — for 100+ leads, pass `?stage=` to the API and let the DB filter. The frontend still needs the full dataset for accurate pill counts — fetch once on each tab click/list refresh.
- **Stage column position** — always between Account and Source, never at the end. The user scans left-to-right: name → company → stage → source → owner.
- **Badge colors are NOT monochrome** — this is the one exception to ARA's monochrome rule. Stage progression needs color differentiation so Greg can scan the pipeline at a glance.

## Search Bars

Client-side filtering pattern (no API call on every keystroke):
1. Store the full data array (`allThreadsData`) on initial load
2. On search input, filter the array by title/name
3. Re-render the filtered subset
4. Show count as "N of M" when filtered

```javascript
.thread-search-wrap input{width:100%;padding:7px 12px 7px 30px;border:1px solid #E5E5E7;border-radius:10px;font-size:13px;font-family:inherit;outline:none;background:#F9F9FB;color:#111;transition:all .15s}
.thread-search-wrap input:focus{border-color:#111;background:#fff;box-shadow:0 0 0 2px rgba(0,0,0,.05)}
```

## Bell Icon and Navigation Notification Pattern

ARA uses a **black SVG bell icon** in the sidebar/header to show urgent human-action items. The bell follows these conventions:

### Bell Icon Design
- **Black SVG with `stroke="#111111"`** — never the 🔔 emoji, never other stroke colors
- Badge shows count as a small red circle with white text, positioned top-right of the bell
- Badge is **visible only when count > 0** — no "0" badge

### What Goes in the Bell vs. What Doesn't

| Shows in bell dropdown | Renders elsewhere |
|------------------------|-------------------|
| ActionItems (qualification reviews, meeting requests, re-engagement flags) | LearningNotifications (skills, coaching, synthesis) → 🧠 Learnings page badge |
| Urgent human tasks only | Scheduled outbound messages → 📋 Activities page |
| | Cron jobs / system actions → 📋 Activities page |

### Polling
- Bell badge polls `GET /api/action-items/stats` every **15 seconds**
- The stats endpoint returns `{"open": N, "resolved": N, "dismissed": N, "overdue": N}`
- Badge displays `overdue + open` combined count (June 2026 change — was just `open` before overdue detection was added)

### Dropdown Content
- Header: **"🔔 Actions"** label (not "Notifications")
- Each ActionItem shows: title, description, relative time, source lead name
- Each item has a **✓ Done** button → `PATCH /api/action-items/{id}` with `{"status": "resolved"}`
- Footer has **"Dismiss all"** button → sends PATCH for all open items
- Dropdown closes on outside click and on item action

### SVG HTML (canonical):
```html
<svg id="bellIcon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#111111" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="cursor:pointer">
  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
  <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
</svg>
<span id="bellBadge" class="bell-badge" style="display:none">0</span>
```

## Actions Page (June 2026 — merged from Actions + Activities)

Actions and Activities are now a single unified page: `onclick="showPage('actions')"`. The sidebar has one "Actions" nav item. No separate Activities page exists.

The Actions page has three tabs:
| Tab | Shows | Data source |
|-----|-------|-------------|
| **Tasks** (default) | Human-actionable items only (open, overdue) — never resolved/completed | `/api/activities` → filtered to `type=action_item` with active status |
| **Recurring** | Cron jobs (morning briefing, end-of-day, health checks, etc.) | `/api/system-jobs` → reads `cron_manifest.json` fallback |
| **History** | Resolved/completed/dismissed tasks | `/api/action-items?status=resolved` |

### Task Rendering
Tasks are rendered as a table with columns: Lead (linked) | Description | Owner (Human/Ava) | Status (color-coded) | Due Date | Actions (⋮ dropdown: Edit, Mark Done, Delete). Overdue items get red dot and `status: "overdue"`.

### Recurring Tab
Shows all 9 Hermes cron jobs (morning briefing, end-of-day WhatsApp, conversation learning extraction, weekly synthesis, gateway health check, daily watchdog, error watcher, WhatsApp queue drain, LLM smoke test). The cron manifest at `/opt/ara/cron_manifest.json` is the fallback when `hermes cron list` fails.

### Design Rules
1. Tasks tab excludes resolved/completed — only open/overdue items appear
2. Never change the table format — no cards, no flex layouts

### Debugging Reference
See `references/action-id-debugging.md` for the `action_` ID prefix mismatch investigation, execution_state anomaly tracing, and the silent 404 bug pattern (`.detail` vs `.error`).
### Why One Page (June 2026 — Merged)
Actions and Activities were merged into a single "Actions" page. The sidebar has only ONE nav item: `onclick="showPage('actions')"`. No separate Activities page exists. All human-actionable tasks, system cron jobs, and history live under the unified Actions page with three tabs: Tasks, Recurring, History.

### Design Rules
1. **No ActionItems on the Activities page** — there is no Activities page anymore. Tasks tab shows ActionItems; Recurring tab shows cron jobs; History shows resolved items.
2. **No scheduled/cron items in the bell dropdown** — bell is for ActionItems only
3. **Learning page badge** (🧠 Learnings sidebar) shows LearningNotification count — this is a simple count badge, NOT a bell dropdown
4. **Bell badge + sidebar badge can both be present** — they show different counts (ActionItems vs LearningNotifications)
5. **Task rendering is TABLE format, never cards** — columns: Lead | Description | Owner | Status | Due Date | ⋮
6. **Never touch dashboard.js styling/rendering when adding backend features** — new data flows through existing APIs and existing UI patterns
