# Sprint 3 — History Tab Regression

**Date:** June 20, 2026
**Bug:** History tab showed "No history yet" despite 27 resolved items in DB
**Root cause:** Sprint 2 changed `/api/action-items` default filter from legacy-status to open-only (`outcome_state IS NULL`). The history tab called the same endpoint with the default filter — expected resolved/cancelled items, got zero. API returned 200 with empty data, no error.

## Affected code
**File:** `/opt/ara/static/dashboard.js`, function `renderHistoryTab()`
**Line:** `var ar = await fetch('/api/action-items?limit=100');`

## Fix
```javascript
// BEFORE (broken):
var ar = await fetch('/api/action-items?limit=100');

// AFTER (fixed):
var ar = await fetch('/api/action-items?status=resolved&limit=100');
var ar2 = await fetch('/api/action-items?status=dismissed&limit=100');
var items = ar.ok ? await ar.json() : [];
if (ar2.ok) { items = items.concat(await ar2.json()); }
```

## Audit checklist — every consumer of `/api/action-items` default filter

When the default filter of an endpoint changes, audit EVERY client-side caller:

- [ ] History tab — calls default → expects resolved items → BROKEN
- [ ] Lead-view actions — calls with ref_id → needs `action_type != 'pending_confirmation'`
- [ ] Agent context builder — server-side, already fixed in Sprint 2
- [ ] Stats endpoint — server-side, already fixed in Sprint 2
- [ ] Pending tab — calls default → expects open items only → OK
- [ ] Scheduled actions — separate endpoint, no overlap

## Lesson
A filter change that passes `?status=resolved` and the default returns `?status=open` is a breaking API change for every consumer that relied on the old default. Audit every caller before shipping.
