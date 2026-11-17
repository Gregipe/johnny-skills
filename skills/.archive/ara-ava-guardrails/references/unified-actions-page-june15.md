# Unified Actions Page — Dashboard Consolidation (June 15, 2026)

## What was replaced

Two separate pages sharing 80% of the same data:

| Old | Route | API |
|-----|-------|-----|
| `renderActivities` — "⚡ Actions Command Centre" | `/activities` | `/api/actions` + `/api/system-jobs` |
| `renderActions` — "Actions" | `/actions` | `/api/action-items/stats` + `/api/action-items` |

## What was built

Single `renderActionsPage()` with three tabs, loaded via `renderActivities()`:

| Tab | API | What |
|-----|-----|------|
| 📋 Pending | `/api/actions?owner=&due_window=&offset=` | One-time ActionItems with filters + pagination |
| 🔄 Recurring | `/api/system-jobs` | Hermes cron jobs + DB ScheduledActions |
| 📜 History | `/api/action-items?limit=100` | Completed, cancelled, resolved, fired |

Routing: both `/activities` and `/actions` hash routes now go to `renderActivities()` → `renderActionsPage()`.

## New features

- **"+ New Action" button** — top-right of page header, works from any tab
- **Lead picker** — autocomplete input calling `/api/leads/search?q=`. Lead is optional (leave blank for system-level actions)
- **Type toggle** — one-time (due date + time) vs recurring (frequency + time)
- **Post-reload after create** — modal closes → `renderActionsPage()` refreshes

## API additions

`POST /api/system-jobs` — creates a `ScheduledAction` with cron config directly from the UI. Accepts `{title, message, frequency, time, action_type}`.

## Files modified

- `static/dashboard.js` — `renderActivities()`, `renderActions()`, `showAddActionForm()`, `showNewActionForm()`, `_toggleActionType()`, `_selectLeadForAction()`, `submitNewAction()`
- `server.py` — `POST /api/system-jobs` endpoint (~line 7126), removed `ref_type=="lead"` filter from `GET /api/actions` (line 2656)
- `dashboard_template.py` — cache-buster `v=19`

## Key field mappings

| Display | API Field | Source Endpoint |
|---------|-----------|----------------|
| Lead column (Pending tab) | `lead_id`, `lead_name` | `/api/actions` (ActionItem) |
| Lead column (History tab) | `ref_id` → fetch `/api/leads/{id}` | `/api/action-items` |
| Lead column (Recurring tab) | N/A — cron jobs don't show lead | `/api/system-jobs` |

## Pitfalls

1. **Lead column shows raw GUIDs** — using `a.ref_id` instead of `a.lead_id`/`a.lead_name`. The two APIs return different field names.
2. **Lead autocomplete returns 404** — the endpoint is `/api/leads/search?q=`, NOT `/api/leads?search=`.
3. **"+Add Action" shows GUID** — don't set input value to raw `esc(leadId)`. Leave blank and async-fetch `/api/leads/{id}` to pre-fill.
4. **Browser cache** — always bump `?v=N` in `dashboard_template.py` when modifying `dashboard.js`.
5. **Conflicting `/api/actions` endpoints** — two exist at lines 2642 and ~6843. The first-defined wins (ActionItem schema). Any new endpoint at this path will shadow both.
6. **System actions excluded** — the old endpoint had `ActionItem.ref_type == "lead"` filter. Removed so non-lead actions appear.
