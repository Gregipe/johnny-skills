# ActionItem State Drift — Debug Playbook

## The problem

ActionItem has three state fields that must stay consistent but drift:
- `status` — display state (open, resolved, dismissed)
- `outcome_state` — what happened (resolved, cancelled, None)
- `execution_state` — execution phase (pending, fired, completed, cancelled)

When they drift (`outcome_state="resolved"` but `status="open"`), different API endpoints
filter on different fields, so the SAME action looks ACTIVE on one page and DONE on another.

## Detection query

```sql
SELECT id, title, status, outcome_state, execution_state
FROM action_items
WHERE outcome_state IS NOT NULL
AND (outcome_state != status OR (outcome_state = 'resolved' AND status != 'resolved'))
ORDER BY created_at DESC;
```

## Root causes of drift

1. **`/api/action-items/{id}` PATCH (line 8343)** — only sets `status`, never `outcome_state`.
   Frontend "Mark Done" calls this. Fix: set `outcome_state` too when status=resolved/dismissed.

2. **`/api/actions/{id}` PATCH (line 2761)** — sets both `outcome_state` and `status` properly,
   but a code change that forgets `outcome_state` assignment creates drift.

3. **Ava's `update_action` tool** — can set `outcome_state` directly but may not set `status`.

## Debugging "actions disappeared" reports

When Greg says actions disappeared:
1. Check `agent_chat_messages` for the last pending-action query (timezone: IST is UTC+5:30).
2. Extract the list of action titles Ava reported as pending at that time.
3. Query those actions in DB — check all three state fields.
4. If `outcome_state="resolved"` but `status` was `"open"` → state drift. Ava's tool reads
   `status` (saw them as pending), fixed endpoint reads `outcome_state` (sees them as resolved).

## June 2026 example

Greg queried pending tasks via WhatsApp at 8:03 AM IST (02:33 UTC). Ava reported 4:
- Catchup today — Ramgopal Nanda (outcome=None ✓, truly pending)
- Close deployment timeline — Amardeep (outcome=resolved, status was open ✗)
- Send Infosec — Jimmie (outcome=resolved, status was open ✗)
- Check in on team — Prashant (outcome=resolved, status was open ✗)

The 3 "disappeared" actions were already resolved. Ava's tool read `status` (still "open"),
so she reported them as pending. The new activities filter reads `outcome_state` ("resolved"),
so they correctly disappeared from the Actions page. Fix: synced status←outcome_state.
