# Voice Staging NameError Loop — July 12, 2026

## Symptom

Ava entered an "infinite loop" when trying to update an action's `due_at` field via voice.
The user asked to change "Chat on commercials with Devashish Sarin" from 6 PM to 11 AM IST.
Ava repeatedly tried `update_action` but nothing changed.

## Root Cause

Two bugs in `/opt/ara/server.py`:

1. **`_BUILD_DESC_FALLBACK_COUNT` never initialized.** Used at line 7010 as a dict
   (`_BUILD_DESC_FALLBACK_COUNT.get(name, 0) + 1`) but never assigned `= {}` anywhere.
   Exists ONLY on lines 7010-7011 in the entire codebase.

2. **`update_action` has no explicit case in `_build_pending_description()`.**
   The function has explicit elif cases for ~16 tools (create_lead, send_whatsapp,
   update_lead_stage, etc.) but `update_action` is NOT among them.

## Failure Chain

1. Ava calls `update_action` → voice agent sends to `POST /api/voice/tool` → 200 OK
2. Voice agent stages for confirmation → `POST /api/voice/stage`
3. `voice_stage()` (line 13077) calls `_build_pending_description(_normalised)`
4. No `elif name == "update_action"` case → falls to generic `else` branch
5. `else` branch at line 7010: `_BUILD_DESC_FALLBACK_COUNT.get(name, 0)` → NameError
6. 500 Internal Server Error returned
7. LLM sees tool call failed → retries with different formats → same 500
8. Repeated 7 times (04:15:11–04:15:44 UTC), then LLM pivoted to `cancel_scheduled` (which HAS an explicit case)

## Evidence

```
Jul 12 04:15:11 ... POST /api/voice/tool HTTP/1.1 200 OK
Jul 12 04:15:11 ... POST /api/voice/stage HTTP/1.1 500 Internal Server Error
  File "/opt/ara/server.py", line 13077, in voice_stage
    _description = _build_pending_description(_normalised)
  File "/opt/ara/server.py", line 7010, in _build_pending_description
    _BUILD_DESC_FALLBACK_COUNT[name] = _BUILD_DESC_FALLBACK_COUNT.get(name, 0) + 1
  NameError: name '_BUILD_DESC_FALLBACK_COUNT' is not defined
```

Pattern repeated 7 times. After 7th failure, LLM switched to `cancel_scheduled`:
```
Jul 12 04:15:48 ... POST /api/voice/stage HTTP/1.1 200 OK  (cancel_scheduled succeeded)
```

DB state after: action `091d69f6` still at `due_at = 2026-07-13 12:30:00 UTC` (unchanged).

## Affected Tools

Any tool in `VOICE_WRITE_TOOLS` (~32 tools) without an explicit elif case in
`_build_pending_description()` would trigger this crash. Known affected:
- `update_action`
- `update_deal`
- `schedule_follow_up`
- `schedule_message`
- `schedule_email`
- `send_attachment`
- `send_internal_note`
- `mark_meeting_booked`
- `evaluate_qualification`
- `log_insight`
- `save_learning`
- `add_to_watchlist`
- `resolve_watchlist_item`
- `import_leads_from_text`
- `upload_document`

## Fix (applied July 12, 2026)

1. Initialize `_BUILD_DESC_FALLBACK_COUNT = {}` at module level (after `_cf_log` at line 322)
2. Add explicit `elif name == "update_action":` case in `_build_pending_description()`
3. Commit: `d8f3ff6` on ARA server

## Verification

After fix, `POST /api/voice/stage` with `update_action` returns 200:
```
{"ok":true,"pending_id":"bf5bdbe4","description":"✏️ Update action: 091d69f6 to Jul 13 at 05:30 AM — shall I update?"}
```
