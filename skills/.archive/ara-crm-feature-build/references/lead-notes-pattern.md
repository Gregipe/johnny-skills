# Lead Notes Pattern

Structured notes on leads with timestamped entries, backend appending logic, structured frontend rendering, quick-add inline form, and edit-mode inclusion.

## Notes Storage Format

Each note entry is a single line in the `Lead.notes` Text column:

```
[timestamp] Type: content
```

Types:
- `Stage ... → ...` — Auto-generated from `update_lead_stage` tool when a `reason` is provided. Icon: 🔄 (green).
- `Note` — User/agent-added context via `update_lead` with `notes` field or quick-add from UI. Icon: 📌 (blue).
- `System` — Auto-generated system events. Icon: ⚙️ (gray).

Example:
```
Initial WhatsApp outreach sent (inbound lead from form).
[Jun 04, 06:30] Stage new → meeting_booked: Greg spoke with Rajesh on the phone
[Jun 04, 06:45] Note: Rajesh mentioned they use Zoho CRM - potential integration angle
```

Legacy lines without `[timestamp] Type:` prefix are rendered as-is with a generic 📋 icon.

## Backend: Notes Appending (Quick-Add) vs Replacing (Edit Mode)

The backend supports two modes via the `notes_action` parameter in the PATCH body:

### Mode A: Append (default) — Used by Quick-Add and Agent Tool Calls

```python
if k == "notes" and v:
    if data.get("notes_action") == "replace":
        # Full replacement from edit mode
        l.notes = v.strip()
    else:
        # Quick-add: append as new entry with timestamp
        existing = l.notes or ""
        _ts = datetime.now(IST_TZ).strftime("%b %d, %H:%M")
        entry = f"[{_ts} IST] Note: {v.strip()}"
        l.notes = (existing + "\n" + entry) if existing else entry
```

### Mode B: Replace — Used by Edit Mode in the Dashboard

When `saveLead()` in the frontend saves from edit mode, it adds `notes_action: 'replace'` to the request body:

```javascript
// In saveLead():
if (data.notes !== undefined) data.notes_action = 'replace';
```

This causes the backend to overwrite the entire `notes` field instead of appending. This is intentional — edit mode shows the full accumulated notes and the user expects to save their edited version, not append another copy of everything.

**When to use each mode:**
- Quick-add (+ Add Note button) → append (default)
- Agent tool call (`update_lead` with `fields: {notes: "..."}`) → append (default)
- Edit mode (inline edit on lead detail card) → replace (`notes_action: 'replace'`)

### update_lead tool in execute_tool (server.py:3643)

Same appending logic — when the Ava agent calls `update_lead` with `fields: {notes: "..."}`:

```python
if k == "notes" and v:
    existing = lead.notes or ""
    _ts = datetime.utcnow().strftime("%b %d, %H:%M")
    entry = f"[{_ts}] Note: {v.strip()}"
    lead.notes = (existing + "\n" + entry) if existing else entry
```

### update_lead_stage tool (server.py:4543)

Already appends stage change reasons as notes with `[timestamp] Stage old → new: reason` format. This pattern was the original inspiration.

### Agent Tool Schema

The `update_lead` tool description (in `AGENT_TOOL_SCHEMA`) should clarify the appending behavior:

```
**update_lead** — Update lead fields. ... NOTE: If you include "notes" in fields, it gets APPENDED to existing notes with a timestamp — use this to record context/insights.
```

When Greg provides context about a lead via WhatsApp ("Rajesh uses Zoho CRM"), Ava should call `update_lead` with `fields: {notes: "Rajesh mentioned they use Zoho CRM"}` to append it to the lead's notes.

## Frontend: Structured Notes Rendering

### Parsing (renderNotesHTML() in static/dashboard.js)

Each line is parsed with:
```javascript
var match = line.match(/^\[(.+?)\]\s+(.+?):\s+(.+)/);
```

- `match[1]` = timestamp (e.g., "Jun 04, 06:30")
- `match[2]` = type (e.g., "Stage new → meeting_booked", "Note", "System")
- `match[3]` = content text

Type detection:
- `type.indexOf('Stage') === 0` → 🔄 stage change
- `type.indexOf('Note') === 0` → 📌 manual note
- `type.indexOf('System') === 0` → ⚙️ system event
- Default → 📝

### HTML Structure per Entry

```html
<div class="note-entry">
  <div class="note-marker note-type-stage">🔄</div>
  <div class="note-body">
    <div class="note-header">
      <span class="note-type note-type-stage">Stage new → meeting_booked</span>
      <span class="note-time">Jun 04, 06:30</span>
    </div>
    <div class="note-content">Greg spoke with Rajesh on the phone</div>
  </div>
</div>
```

### Container

```html
<div class="notes-container">
  <div class="notes-toolbar">
    <span class="notes-count">4 entries</span>
    <button class="lead-btn" onclick="quickAddNote('leadId')">+ Add Note</button>
  </div>
  <div class="notes-list">
    <!-- note-entry elements -->
  </div>
</div>
```

### CSS Classes

| Class | Purpose | 
|-------|---------|
| `.notes-container` | White card with border, rounded 20px, padding 20px |
| `.notes-toolbar` | Flex row with count + add button, bottom border separator |
| `.notes-list` | Flex column with 8px gap between entries |
| `.note-entry` | Flex row with 12px gap, 12px padding, light gray background, rounded 12px, subtle border |
| `.note-marker` | 28×28px circle, center-aligned icon |
| `.note-marker.note-type-stage` | Green background (#ECFDF5) |
| `.note-marker.note-type-note` | Blue background (#EFF6FF) |
| `.note-marker.note-type-system` | Gray background (#F5F5F7) |
| `.note-body` | flex:1, min-width:0 |
| `.note-header` | Flex row with justify-content:space-between |
| `.note-type` | 10px uppercase label, 2px 8px padding, rounded 6px |
| `.note-time` | 11px, #9A9A9E |
| `.note-content` | 13px, #111, line-height 1.5, white-space:pre-wrap |

### Empty State

When no notes exist, show "No notes yet." with a + Add Note button.

## Frontend: Quick-Add Note

### Trigger

"+ Add Note" button in the notes toolbar → calls `quickAddNote(leadId)`.

### Inline Form

```javascript
function quickAddNote(leadId) {
  var form = document.createElement('div');
  form.id = 'quickNoteForm';
  form.className = 'quick-note-form';  // Blue border (#2563eb), rounded 16px, box-shadow
  form.innerHTML =
    '<div class="quick-note-header">Add Note</div>' +
    '<textarea class="quick-note-input" placeholder="Type your note..." rows="3"></textarea>' +
    '<div class="quick-note-actions">' +
      '<button class="form-btn primary" onclick="saveQuickNote(\'' + leadId + '\')">Save</button>' +
      '<button class="form-btn secondary" onclick="this.parentElement.parentElement.remove()">Cancel</button>' +
      '<span class="form-status" id="quickNoteStatus"></span>' +
    '</div>';
  container.parentElement.insertBefore(form, container.nextSibling);
}
```

### Save

```javascript
async function saveQuickNote(leadId) {
  var note = textarea.value.trim();
  // PATCH /api/leads/{leadId} with {notes: note}
  // On success: re-fetch lead, re-render notes tab with renderNotesHTML()
}
```

## Frontend: Edit-Lead Notes Inclusion

When entering edit mode (`toggleEditLead`), fetch current notes from the API and add a textarea at the bottom of the lead card:

```javascript
fetch('/api/leads/' + leadId).then(function(r) { return r.json(); }).then(function(l) {
  var notesSection = document.createElement('div');
  notesSection.className = 'lead-card-section lead-notes-edit';
  notesSection.innerHTML = '<h4>Notes</h4>' +
    '<textarea class="lead-edit-textarea" data-field="notes" rows="4">' + 
    escHtml(l.notes || '') + '</textarea>';
  card.querySelector('.lead-card-inner').appendChild(notesSection);
});
```

The `saveLead()` function already collects `.lead-edit-textarea` values, so `data.notes` is sent as part of the PATCH body, which the backend appends.

## API Endpoints Affected

| Endpoint | Change |
|----------|--------|
| `PATCH /api/leads/{lead_id}` | Notes appends with timestamp instead of overwrite |
| `POST /api/agent/chat/{tenant_id}` (via execute_tool → update_lead) | Same appending logic for agent tool calls |

## Files Modified (From This Session)

| File | Change |
|------|--------|
| `server.py` | `update_lead` endpoint (line 828) — notes append logic |
| `server.py` | `update_lead` tool in execute_tool (line 3643) — notes append logic |
| `server.py` | `AGENT_TOOL_SCHEMA` — updated tool description for notes |
| `static/dashboard.js` | `renderNotesHTML()` — structured notes rendering |
| `static/dashboard.js` | `quickAddNote()` / `saveQuickNote()` — inline quick-add |
| `static/dashboard.js` | `toggleEditLead()` — fetch notes + add textarea |
| `static/dashboard.js` | `escHtml()` — XSS-safe HTML escaping helper |
| `dashboard_template.py` | CSS for all new note components |
