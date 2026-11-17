# Lead Detail Tabs & Actions

The lead detail page (`showLeadDetail()` in `static/dashboard.js`) has a 3-tab bar below the lead card: **Outreach**, **Actions**, **Notes**.

## Tab Bar Structure

```javascript
'<div class="tab-bar">' +
  '<div class="tab-item active" data-action="switch-tab" data-tab="outreach">Outreach</div>' +
  '<div class="tab-item" data-action="switch-tab" data-tab="actions">Actions</div>' +
  '<div class="tab-item" data-action="switch-tab" data-tab="notes">Notes</div>' +
'</div>' +
'<div id="leadOutreach">...merged timeline + scheduled outbound...</div>' +
'<div id="leadActions" style="display:none">...action cards...</div>' +
'<div id="leadNotesTab" style="display:none">...notes...</div>'
```

**Pattern:**
- Tab items: `data-action="switch-tab"` + `data-tab="name"`
- Each tab panel is a `<div>` with `id="lead[Name]"` (camelCase: `leadOutreach`, `leadActions`, `leadNotesTab`)
- Default tab is `active`, its panel is visible; others `style="display:none"`

## Tab Switching Function

```javascript
function switchLeadDetailTab(tab) {
  document.querySelectorAll('.tab-bar .tab-item').forEach(function(t) {
    t.classList.toggle('active', t.dataset.tab === tab);
  });
  var oa = document.getElementById('leadOutreach');
  var ac = document.getElementById('leadActions');
  var nt = document.getElementById('leadNotesTab');
  if (oa) oa.style.display = tab === 'outreach' ? 'block' : 'none';
  if (ac) ac.style.display = tab === 'actions' ? 'block' : 'none';
  if (nt) nt.style.display = tab === 'notes' ? 'block' : 'none';
}
```

## Tab Contents

### Outreach Tab — `renderOutreachTab(l, convs)`
Merges the old Timeline + Outreach Activity into one chronological feed:
- **Conversations** (inbound/outbound) — channel icon, direction label, timestamp, content
- **Scheduled outbound** — shown as forward-dated markers with dashed border, grey italic text
- Items sorted chronologically. Empty state: "No outreach history yet..."

### Actions Tab — `loadActionsForLead(leadId)`
Fetches `GET /api/actions/{lead_id}` and renders action cards:
- **Approval controls** for Ava-owned gated actions: ✓ Approve / ✗ Reject buttons (black/white theme)
- **Mark Done** for human-owned pending actions
- **Resolved cards** grey out with reduced opacity
- **Add Action** CTA via `showAddActionForm(leadId)` — prompt-based form

Action card CSS classes: `.action-card`, `.action-card.resolved`, `.action-card-header`, `.action-owner`, `.action-due`, `.action-card-title`, `.action-card-desc`, `.action-card-meta`, `.action-card-controls`

### Notes Tab — `renderNotesHTML(notesText, leadId)`
Unchanged. Structured notes with timestamps and type markers.

## JavaScript onclick Escaping Pitfall

When building HTML inside JavaScript string concatenation (`container.innerHTML = '...' + var + '...'`), **never** embed dynamic values in `onclick` via the `\'` escape pattern. The `\'` inside a JS string that itself generates HTML will break the outer string.

**Fix:** Use `data-` attributes:
```javascript
// ❌ BROKEN
onclick="showAddActionForm(\' + leadId + \')"

// ✅ CORRECT
data-lead-id="' + leadId + '" onclick="showAddActionForm(this.dataset.leadId)"
```

See `shared-ui-propagation/references/js-onclick-escaping.md` for full explanation.

## Action API

## Critical Pitfalls

### `<script>` Tags in innerHTML — Dead Code

Browsers do NOT execute `<script>` tags inserted via `innerHTML`. When `showLeadDetail()` sets `cp.innerHTML = '...<script>loadActionsForLead(\'' + l.id + '\');</script>'`, the script **never runs**. The Actions tab stays stuck on "Loading actions…" forever.

**Fix:** Call async functions directly after `innerHTML` assignment:

```javascript
cp.innerHTML = '...<div id="leadActions">...</div>';
loadActionsForLead(l.id);  // ← direct call, not a <script> tag
```

### onclick Escaping via JS String Concat

Never embed dynamic values in `onclick` via backslash-escaping. Use `data-` attributes:

```javascript
// ❌ BROKEN — \\' double-escape breaks the outer JS string
onclick=\"showAddActionForm(\\' + leadId + '\\')\"

// ✅ CORRECT — reads from the element's own dataset
data-lead-id=\"' + leadId + '\" onclick=\"showAddActionForm(this.dataset.leadId)\"
```

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/actions/{lead_id}` | GET | Open + recent actions for a lead |
| `/api/actions` | POST | Create new action |
| `/api/actions/{action_id}` | PATCH | Update state (approve/reject/resolve) |
| `/api/actions` | GET | Global command centre with filters |

## API: Lead Response with Next Action

```json
{
  "next_action": {"title": "Call Rajesh", "due_at": "2026-06-15T10:00:00", "execution_state": "pending", "owner": "human"},
  "scheduled_actions": [...]
}
```
