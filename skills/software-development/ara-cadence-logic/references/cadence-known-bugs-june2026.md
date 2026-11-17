# Cadence Bugs Found (June 13, 2026)

## Bug 1: `lead.industry` AttributeError in email generation

**File:** `app/services/cadence.py:254`
**Introduced:** May 24 (commit `72ad91f1`)

```python
Industry: {lead.product_interest or lead.industry or 'Not specified'}
```

The `Lead` model has no `industry` field. Every email generation hits this AttributeError before ever reaching the Gmail send step.

**Fix:** Replace `lead.industry` with `lead.product_interest`:
```python
Industry: {lead.product_interest or 'Not specified'}
```

**Impact:** 12 failed actions (3 retries × 4 action batches) for Gregory Ipe. Created 5 `action_failed` LearningNotifications. Zero alerts to Greg.

---

## Bug 2: `resolve_lead` filters archived leads before trigger_cadence stage check

**File:** `server.py:3388` (trigger_cadence handler)
**Introduced:** Pre-existing (default behavior of `resolve_lead`)

```python
lead = resolve_lead(lead_name, db)
# Default: include_archived=False — filters out archived leads silently
if lead.stage == "archived":
    return ToolResult.fail(...)
```

`resolve_lead()` defaults to `include_archived=False`, so archived leads are excluded by the SQL query. The archived-stage check on the next line never fires — instead the caller gets `AmbiguousLeadError: Lead 'X' not found`.

**Fix:** Pass `include_archived=True`:
```python
lead = resolve_lead(lead_name, db, include_archived=True)
```

**Also affected:** `attach_to_deal` at line 3066 (same pattern, fixed in same session).

---

## Bug 3: Email channel skips stage advancement

**File:** `server.py:_execute_action()` (~line 7093)
**Introduced:** Pre-existing

```python
if channel == "whatsapp":
    ...
    if lead.stage == "new":
        lead.stage = "reached_out"   # ✅ WhatsApp advances
elif channel == "email":
    # Send email via Gmail API
    # ❌ No stage advancement
elif channel == "call":
    ...
```

Only the WhatsApp branch advances `new` → `reached_out`. Email-only cadences never advance the lead's stage, so the lead can cycle through multiple email steps while staying at `new`. This also means `get_lead_detail` and the pipeline context disagree — the context shows `new` (correct after email sent) but a fresh tool read shows whatever the last advancement was.

**Fix:** Add the same advancement in the email and call branches after a successful send.

---

## Bug 4: Failed actions never push to Greg

**File:** `server.py:_run_scheduler()` (~line 7587)
**Introduced:** Pre-existing

When a scheduled action permanently fails:
1. ✅ Creates `LearningNotification(type="action_failed")` 
2. ❌ Never calls `_notify_owner()` to push a WhatsApp alert
3. ❌ Never adds to `AvaWatchlist` (which IS injected into pipeline context)
4. The notification is only fetchable via `/api/learning/notifications` — Greg must know to check

The `LearningNotification` → `AvaWatchlist` bridge doesn't exist for failed actions. The `watchlist_context` injection at line 4932 only reads from `AvaWatchlist`, not `LearningNotification`.

**Fix:** Either:
- Call `_notify_owner()` from `_run_scheduler()` on permanent failure
- Or convert `action_failed` LearningNotifications into `AvaWatchlist` entries
