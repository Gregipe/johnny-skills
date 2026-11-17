# Cadence Debugging — Complete Failure Mode Reference

## Failure Mode Matrix

| Error / Symptom | Likely Cause | Check / Fix |
|----------------|-------------|-------------|
| `no cadence_type` | Lead has NULL `cadence_type` | Auto-assign via `determine_cadence()` in trigger endpoint |
| `no config for {type}` | Template was never published | Check `sqlite3 ara.db "SELECT template_id FROM cadence_configs;"` — publish via UI or API |
| `no steps` | Template has empty `steps` array | Add steps and re-publish |
| `stage={stage}` | Lead is at engaged+ stage, gate blocks | Reset stage to `reached_out` (trigger endpoint does this) |
| `{N} pending actions exist` | Lead already has pending actions | Trigger endpoint cancels old ones first; false positive from double-trigger |
| HTTP 500 / unknown error | Transient backend glitch | **Restart server first.** Then test direct API call |
| Ava says "not set up" but template exists | Template published, lead side issue | Check `lead.cadence_type` — if NULL, needs backfill |
| Ava says "not set up" AND template + lead correct | Transient error, server restart resolves | See "Transient Backend Error" below |
| All N email repeats same `scheduled_at` | Cascade collapse (old bug, fixed May 30) | Each repeat computed from `now` independently + working hours pushed all to same slot. Fixed: cascade from previous adjusted time |
| First step appears delayed (e.g., scheduled 1h later despite `delay_hours=0`) | **First repeat (r=0) already fired and failed.** The scheduler correctly scheduled it at `now`, but the send failed (e.g., Gmail OAuth not connected). The user sees repeat r=1 as the "first" pending action and assumes it was delayed. | Check ALL statuses for the lead — look for a `failed` entry with r=0 at the trigger time. The `delay_hours` logic is correct; the issue is that the immediate step failed silently. Fix the underlying integration, then re-trigger. |
| WhatsApp sends silently fail | `wa.send()` used instead of `wa.send_message_sync()` | Fix in `_execute_action()` — all 4 instances |
| Actions show "completed" but message never received | Send result not checked | Fix: check return value of `send_message_sync()` / `send_via_gmail_api()` |
| Conversation not logged after outbound send | SQLite lock from concurrent session | Fix: use passed-in `db` session, not `init_db()` |
| Step desc sent as literal text instead of LLM instruction | `desc` + `fields` coexisting in step config | Remove `fields` from steps that have `desc` — they're mutually exclusive |

## Transient Backend Error (June 2026)

**Symptom:** Ava reports "the system returned an error" or "the cold cadence hasn't been set up" BUT both the template AND the lead's `cadence_type` are correct. The tool call itself threw an exception (HTTP 500, `UnboundLocalError`, DB lock), not a logic-level rejection.

### Debug flow:

1. **Verify template is published:**
   ```bash
   sqlite3 ara.db "SELECT template_id, length(config) FROM cadence_configs;"
   ```

2. **Verify lead has `cadence_type`:**
   ```bash
   sqlite3 ara.db "SELECT cadence_type FROM leads WHERE id='LEAD_ID';"
   ```

3. **Test trigger directly via API** (bypasses Ava's tool layer):
   ```bash
   curl -s -X POST "http://localhost:8766/api/cadence/trigger/lead/LEAD_ID" | python3 -m json.tool
   ```

4. **If direct API succeeds but Ava's tool failed** → transient glitch. Restart server.

5. **If direct API also fails with 500** → backend code bug. Check `server.py` for recent changes, `UnboundLocalError` from local imports, or DB migration issues.

### Root causes (all resolved):
- `UnboundLocalError` from local imports shadowing module-level names (May 30 fix)
- SQLite `database is locked` from concurrent sessions in scheduler (May 30 fix)
- General server uptime drift after repeated start/stop cycles

### Stale cancelled action cleanup

After repeated start/stop cycles, the `scheduled_actions` table accumulates cancelled records for a single lead. While these don't block scheduling, they bloat the DB:

```bash
# Check count
sqlite3 ara.db "SELECT status, COUNT(*) FROM scheduled_actions WHERE lead_id='LEAD_ID' GROUP BY status;"

# Clean up (optional — doesn't affect functionality)
sqlite3 ara.db "DELETE FROM scheduled_actions WHERE lead_id='LEAD_ID' AND status='cancelled';"
```

## Lead-Side Diagnostics

### NULL cadence_type (Pre-May 24 leads)

Leads created before `determine_cadence()` auto-assignment was implemented have NULL `cadence_type`. The trigger returns `reason: "no cadence_type"` silently.

**Fix:** Auto-assignment now runs in `trigger_cadence_for_lead()` and backfills via migration in `lifespan()`:
```python
if not lead.cadence_type:
    lead.cadence_type = determine_cadence(lead.lead_source or "form", "reached_out")
```

### Lead has wrong cadence_type

If the lead has `cadence_type=cold` but you want `inbound` (or vice versa), update it:
```bash
curl -s -X PATCH 'http://localhost:8766/api/leads/LEAD_ID/cadence' \
  -H 'Content-Type: application/json' \
  -d '{"cadence_type": "cold"}'
```

### Cadence Type Mapping Rules

```python
CADENCE_MAPPING = [
    (lambda s, st: s in ('form','meta','google','referral') and st != 'dormant', 'inbound'),
    (lambda s, st: st in ('dormant','lost'), 'nurture'),
]
# Fallback: everything else → 'cold'
```

## Verification After Fix

```bash
curl -s -X POST "http://localhost:8766/api/cadence/trigger/lead/LEAD_ID" | python3 -m json.tool
# Expected: {"scheduled": N, "cadence_type": "cold|inbound|nurture", ...}
# If scheduled=0, check the "note" field for the reason
```

## Full System Prompt Diagnostics

When emails come out generic:

```bash
# Check if systemPrompt is populated in DB
sqlite3 ara.db "SELECT template_id, \
  json_extract(config, '$.systemPrompt') IS NOT NULL AS has_sysprompt, \
  length(COALESCE(json_extract(config, '$.systemPrompt'), '')) AS len \
  FROM cadence_configs;"
```

If `len` is 0 for all templates → global prompt was never published to backend. Open `/cadence`, click "✎ Open Builder", and "Save & Close" to publish.

## Email Signature Verification

```bash
cd /Users/greg/ara && python3 -c "
import json, sqlite3
db = sqlite3.connect('ara.db')
for t in ['cold','inbound','nurture']:
    row = db.execute('SELECT config FROM cadence_configs WHERE template_id=?', (t,)).fetchone()
    cfg = json.loads(row[0])
    body = cfg.get('promptParts',{}).get('channelSpecific',{}).get('email',{}).get('body','')
    print(f'{t}: Signature in body={\"## Signature\" in body}')
    sp = cfg.get('systemPrompt','')
    print(f'{t}: Signature in sysprompt={\"**Signature**\" in sp}')
"
```
