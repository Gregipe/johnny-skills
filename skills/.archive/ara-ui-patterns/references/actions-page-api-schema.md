# Actions Page — API Schema Traps (June 15, 2026)

## Two Conflicting /api/actions Endpoints

There are TWO endpoints at the same URL in server.py:

| Line | Returns | Fields |
|------|---------|--------|
| 2642 | ActionItem rows | `lead_id`, `lead_name`, `title`, `owner`, `channel`, `due_at`, `execution_state`, `outcome_state` |
| 6843 | ScheduledAction rows | `lead_id`, `lead_name`, `action_type`, `channel`, `status`, `scheduled_at`, `payload` |

FastAPI resolves to the FIRST-defined route (line 2642). The frontend's Pending tab uses the ActionItem endpoint.

## lead_id vs ref_id Confusion

The two APIs use DIFFERENT field names for the same concept:

| API Endpoint | Lead ID field | Lead name field |
|---|---|---|
| `/api/actions` (ActionItem) | `lead_id` | `lead_name` |
| `/api/action-items` | `ref_id` | (resolved manually via leadCache) |

**Pitfall:** Using `a.ref_id` on Pending tab data — the endpoint returns `lead_id`, so `ref_id` is undefined. Lead column shows raw GUIDs or `—`.

**Fix:** Check which API endpoint the tab uses:
- Pending tab → `/api/actions` → use `a.lead_id`, `a.lead_name`
- History tab → `/api/action-items` → use `a.ref_id`, resolve lead_name from leadCache

## Unified Actions Page (June 15, 2026)

The old separate `renderActivities()` (ScheduledActions + cron jobs) and `renderActions()` (ActionItem cards) were consolidated into one page with three tabs:

| Tab | API | Shows |
|---|---|---|
| Pending | `/api/actions` | One-time actions with owner/due-date filters + pagination |
| Recurring | `/api/system-jobs` | Cron jobs / system jobs |
| History | `/api/action-items` | Completed, cancelled, fired items |

Lead is now optional in the create form — a searchable picker with autocomplete from `/api/leads?search=`.
A One-time / Recurring toggle switches between due date fields and frequency+time fields.
`POST /api/system-jobs` was added for creating crons from the UI.

## system-jobs POST Endpoint

```json
POST /api/system-jobs
{"title": "Reminder", "message": "...", "frequency": "daily", "time": "18:30", "action_type": "whatsapp_to_owner"}
→ {"status": "created", "job_id": "...", "next_run": "..."}
```
