# Leads Table Bulk Actions + Column Refresh

Session: May 24, 2026
Goal: Add checkbox selection, bulk assign/delete, three-dot menu, and column refresh (Owner replacing Status, Next Activity columns) to ARA leads table.

## Changes Made

### server.py
1. **Modified `list_leads()`** — added batch-fetch of next scheduled actions per lead using a single `IN` query instead of N+1. Returns `next_activity_at` and `next_activity_type` fields per lead.
2. **Added `POST /api/leads/bulk-assign`** — takes `{lead_ids: [], agent: "ava"}`. Updates `assigned_agent` on matching leads.
3. **Added `POST /api/leads/bulk-delete`** — takes `{lead_ids: []}`. Deletes scheduled actions first, then the lead (SQLAlchemy cascade handles conversations).

### static/dashboard.js
1. **Rewrote `renderLeads()`** — toolbar now has leads count on left, buttons right-aligned in `.leads-toolbar-right`:
   - 👤 Assign (dropdown with 🤖 Ava + disabled Add SDR)
   - ⋮ (dropdown with 🗑 Delete + disabled 🔀 Merge)
   - + Add Lead (existing)
2. **Rewrote `renderLeadsTable()`** — new column order:
   - Checkbox (select-all header + per-row)
   - Name (with email subtitle)
   - Account (company + phone)
   - Source
   - Owner (replaces Status — shows assigned_agent)
   - Next Activity (from scheduled_actions)
   - Activity Type (humanized via formatActivityType())
   - Created
3. **Added functions:**
   - `toggleSelectAllLeads()` / `updateSelectAllCheckbox()` — select-all logic
   - `getSelectedLeadIds()` — reads all checked checkboxes
   - `toggleAssignDropdown()` / `toggleLeadsDotsMenu()` — dropdown toggles
   - `closeLeadsDropdowns()` — close all
   - `assignSelected(agent)` — bulk-assign via API
   - `bulkDeleteLeads()` — confirm + delete via API
   - `formatActivityType(t)` — maps action_type slugs to readable labels
4. **Patched event delegation** — lead row click handler now skips navigation on:
   - `input[type="checkbox"]` clicks
   - Clicks inside dropdowns
   - Clicks on toolbar buttons

### dashboard_template.py
Added CSS classes:
- `.leads-toolbar-right` — flex container for right-aligned toolbar buttons
- `.leads-assign-btn`, `.leads-assign-btn:hover` — assign button with border
- `.leads-dots-btn`, `.leads-dots-btn:hover` — three-dot button
- `.leads-dropdown` — positioned dropdown with shadow
- `.leads-dropdown-item`, `.disabled`, `.danger` — dropdown item styles
- `input[type="checkbox"]` — global cursor + accent color
- First th/td padding tweak for checkbox column
- `.leads-toolbar` updated to `justify-content: space-between`
- `.leads-count` removed `margin-left: auto`

## Key Design Decisions

- **assigned_agent = owner** — No new DB column. The Owner column simply remaps existing `assigned_agent` display (was displayed as subtitle under Status, now its own column).
- **Single query for next_activity** — Collected all lead IDs, queried scheduled_actions with `IN (lead_ids)`, took the earliest per lead via first-wins dict. Avoids N+1.
- **Outside-click close** — Single `document.addEventListener('click', ...)` checks `closest()` on both dropdown wrappers.
- **Click row navigation preserved** — Row click still navigates to lead detail. Only checkboxes and dropdown UI elements are excluded.

## Future (Noted for Merge feature)

Merge placeholder currently disabled. When real merge is built:
- Needs a merge endpoint that consolidates two leads (pick lead to keep, merge conversations, transfer scheduled actions)
- Frontend: select exactly 2+ leads and pick a "primary" one, or auto-merge into the oldest
