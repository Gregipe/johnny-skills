# Cadence Codebase Pitfalls (June 2026)

## 1. `lead.industry` AttributeError

**File:** `app/services/cadence.py`, line ~254, function `generate_step_message()`

The Lead model has no `industry` column. The correct field on Deal is `industry_segment`.

**Before (crashes):**
```python
Industry: {lead.product_interest or lead.industry or 'Not specified'}
```

**After (fixed):**
```python
Industry: {lead.deal.industry_segment if lead.deal and lead.deal.industry_segment else lead.product_interest or "Not specified"}
```

Hierarchy: deal's `industry_segment` → lead's `product_interest` → "Not specified"

## 2. `_sync_deal_stage_from_lead` Silent Failure

**File:** `server.py`, function `_sync_deal_stage_from_lead()` (~line 7452)

Had `except Exception: pass` — any sync error was invisible. When a deal falls out of sync with its lead (e.g., lead at "reached_out", deal stuck at "new"), there was zero visibility.

**Fixed:** Replaced with `except Exception as e: logging.getLogger("scheduler").warning(...)`.

**Diagnosis:** Check deal events for "Auto-synced from..." entries. If missing but lead stage changed, the sync hit an exception.

## 3. Deal `industry_segment` Mandatory for Manual Creation

**File:** `server.py`, function `create_deal()` (~line 2134)

**Before:** `industry_segment` defaulted to `""` with no validation — deals created without industry.

**After:** Returns `{"error": "industry_segment is required"}` if empty. Auto-created deals (from lead stage-change path) still allow empty.

## 4. Lead Detail API Only Showed Pending Actions

**File:** `server.py`, function `get_lead()` (~line 1193)

**Before:** `scheduled_actions` filtered to `status.in_(["pending", "firing"])`. Actions disappeared from UI when they completed/failed.

**After:** Returns all statuses (pending, firing, completed, failed, cancelled) with `last_error`, ordered by `scheduled_at DESC`, limit 50. The frontend `scheduledActionsHTML()` already renders status dots for all states.

**API field added:** `"last_error": a.last_error[:200] if a.last_error else None`
