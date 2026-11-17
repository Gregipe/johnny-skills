# Daily Brief — Data Endpoint Notes (verified Sep 2026)

Endpoints and schema facts for the 7AM IST daily-brief cron (and any owner-notification job) that
gathers action items / overdue / learnings from ARA. Companion to the "Cron Brief Pattern" section
in SKILL.md.

## Owner phone
- `GET /api/tenants/{id}/settings` can return **HTTP 500 Internal Server Error** during a live run.
  Do not rely on it for the owner phone.
- Reliable source is SQLite:
  ```bash
  sqlite3 "$DB" "SELECT phone FROM users WHERE tenant_id='3e736242' AND role='admin' LIMIT 1"
  ```
  `DB=/Users/greg/ara/ara.db` on macOS.

## Action items
- `GET /api/actions?tenant_id=3e736242` returns all actions as `{actions:[...], total:N}`.
  Every row has `due_at: null` — there is no due-date data on this endpoint.
- The `action_items` table has **no `due_at` column** (schema: `id, tenant_id, action_type, title,
  description, ref_type, ref_id, status, created_at, resolved_at, execution_state`).
- There is **no overdue filter**. Passing `&overdue=true` is silently ignored (returns the same list).
- Consequence: "overdue count" can only be inferred from `created_at` age, not any due-date field.
  Do not claim a due-date-based overdue number. Report "0 overdue" unless you compute age yourself.

## Learnings / insights (last 24h)
- Working endpoint: `GET /api/insights?tenant_id=...` → array of `{id, lead_id, conversation_id,
  insight_type, key, value, confidence, source, created_at}`.
- **404 endpoints:** `/api/learnings` and `/api/learning-notifications` (do not use).
- SQLite fallback tables (both exist):
  - `ava_insights` (cols: `insight_type, key, value, confidence, source, created_at`)
  - `learning_notifications` (cols: `notif_type, title, message, ...`)
  - Last-24h filter: `created_at >= datetime('now','-1 day')`.

## Health endpoint semantics
`GET /api/health` can return `{"system":"down","sc_status":"down","db_status":"ok"}` while the API
still serves requests fine. `system`/`sc_status` reflect the scheduler and WhatsApp sidecar — NOT the
HTTP API. Only `sc_status: down` (together with a send error like `awaiting_scan` / `disconnected`)
actually blocks WhatsApp delivery. Probe `http://localhost:8767/status` directly for the sidecar state.
