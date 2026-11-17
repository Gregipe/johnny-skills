# Confirmation Flow Bugs — June 2026

Four bugs fixed in the confirmation pipeline.

## Bug 1: PENDING_TTL Too Short
**Symptom:** User said "yes" but proposal expired before confirmation received.
**Root cause:** PENDING_TTL was 120 seconds. User's "yes" took 171 seconds.
**Fix:** Changed PENDING_TTL from 120 to 600 seconds (10 minutes).
**Location:** server.py, PENDING_TTL constant.

## Bug 2: Voice Note Ordering — Pre-confirmed Overriding Safeguard
**Symptom:** Voice notes auto-executed without confirmation despite [ACTION: ASK] rule.
**Root cause:** `pre_confirmed` check ran AFTER `voice_note` check, overriding `intent="ask"` back to `intent="now"`.
**Fix:** Reordered checks — voice_note always wins, forces `intent="ask"` + `confirmed=False` regardless of LLM output.
**Location:** server.py, observe loop ~line 5269-5275.

## Bug 3: Action Title = LLM Conversational Text
**Symptom:** Confirmation items showed titles like "You're right — here's the actual proposal with the tool call…" instead of tool descriptions.
**Root cause:** `_pending_row.title` was set to `resp_clean[:60]` — the LLM's conversational response text, not the tool action description.
**Fix:** Now uses `_build_pending_description(data_tools)` for both title and description.
**Location:** server.py, observe loop ~line 5485.

## Bug 4: Confirmation Items Never Get status=resolved
**Symptom:** Executed/rejected confirmation items remained with `status="open"` → showed up in action listings forever.
**Root cause:** Flush path only set `execution_state="fired"` (or "cancelled" on reject) but never `status="resolved"`.
**Fix:** Added `status="resolved"` + `outcome_state="resolved"` in both accept and reject paths.
**Location:** server.py, observe loop ~line 5868 (accept) and ~line 5887 (reject).

## Bug 5: Duplicate GET /api/actions/{id} Routes
**Symptom:** Edit modal never opened — frontend got empty response.
**Root cause:** Two GET /api/actions/{id} endpoints: line 2552 (treated id as lead_id) and line 6973 (treated id as action_id). FastAPI used first match.
**Fix:** Renamed line 2552 to GET /api/leads/{lead_id}/actions, added proper GET /api/actions/{action_id}.

## Bug 6: Fetch Cancelled Actions Shown as Pending
**Symptom:** Jimmie Tete's cancelled action showed as pending.
**Root cause:** API query had `outcome_state != "resolved"` — SQL NULL comparison excluded rows with NULL outcome_state.
**Fix:** Simplified to only filter `execution_state != "cancelled"`. Used SQLAlchemy `or_()` for NULL-safe comparison where needed.

## Bug 7: get_action_items Returning Confirmation Queue Items
**Symptom:** "What are our latest actions?" returned 4 items with 2 garbage ones.
**Root cause:** `get_action_items` filtered on `status="open"` — confirmation items had `status="open"` because Bug 4 never resolved them.
**Fix:** Added `action_type != "pending_confirmation"` filter to exclude internal confirmation entries.
