# Autocomplete Searchable Dropdowns in Dashboard Modals

## The Pattern (Proven June 2026)

When building a searchable lead picker / autocomplete dropdown inside a modal form, follow this pattern:

### 1. HTML: data-attribute-driven dropdown items

```javascript
// Dropdown items use data attributes, NEVER inline onclick
dealLeadDrop.innerHTML = leads.map(function(l) {
  return '<div style="padding:8px 12px;cursor:pointer;..." ' +
    'data-lid="' + l.id + '" data-lname="' + esc(l.name) + '" data-lemail="' + esc(l.email||'') + '">' +
    esc(l.name) + ' <span style="...">' + esc(l.company||'') + '</span></div>';
}).join('');
```

### 2. Click delegation on the dropdown container

```javascript
// Single click listener, walks up to find data-lid
dealLeadDrop.addEventListener('click', function(e) {
  var el = e.target.closest('[data-lid]');
  if (!el) return;
  var id = el.getAttribute('data-lid');
  var name = el.getAttribute('data-lname');
  // ... read other data attributes
  _fillDealLead(id, name, email, phone, title);
});
```

### 3. Scope: INSIDE the modal function, AFTER insertAdjacentHTML

**CRITICAL:** The autocomplete listener MUST be attached after the modal HTML is inserted. Do NOT put it at global scope — the input element won't exist at page load.

```javascript
function showMyModal() {
  // 1. Insert modal HTML
  document.body.insertAdjacentHTML('beforeend', modalHtml);

  // 2. Attach overlay click handler
  var overlay = document.body.lastElementChild;
  overlay.addEventListener('click', function(e) { /* close-modal, etc */ });

  // 3. Attach autocomplete — input NOW exists
  var inp = document.getElementById('myLeadPicker');
  var drop = document.getElementById('myLeadDrop');
  if (inp) {
    inp.addEventListener('input', function() {
      var q = inp.value.trim();
      if (q.length < 2) { drop.style.display = 'none'; return; }
      fetch('/api/leads/search?q=' + encodeURIComponent(q) + '&limit=8')
        .then(function(r) { return r.json(); })
        .then(function(leads) {
          // Build dropdown items with data attributes
        });
    });
    // Hide dropdown on outside click
    document.addEventListener('click', function hideDrop(e) {
      if (!drop.contains(e.target) && e.target !== inp) drop.style.display = 'none';
    });
  }
}
```

## Why Inline onclick Failed Here

The dropdown is built inside a JS `innerHTML` string with single quotes as delimiters. Any inline onclick like:

```javascript
'onclick="_selectDealLead(\'' + l.id + '\',\'' + l.name + '\')"'
```

...produces broken JS when `l.name` contains single quotes (e.g. "O'Brien"). The escaping chain is: Python triple-quoted string → JS string → HTML attribute value → JS code. Each layer consumes backslashes. After the patch tool processes its own escaping, you end up with quadruple-escaped quotes that are impossible to debug.

**The fix is always:** data attributes + event delegation. No inline onclick with arguments.

## The `e.target.closest()` Pattern

Always use `e.target.closest('[data-lid]')` — not `e.target.getAttribute('data-lid')`. The click typically lands on a child `<span>` or text node inside the dropdown item, not the `<div>` itself. `closest()` walks up to find the right element.

## Escaping User Data

Always `esc()` any user-provided data inserted into innerHTML:

```javascript
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
```

## Cache-Buster Reminder

Every dashboard.js change requires bumping `?v=N` in `dashboard_template.py`. Browsers cache static .js aggressively. Without the bump, users see stale code and report bugs that were already fixed.
