# Deal vs Lead Context Fix (June 2026)

## Problem
When Greg asked "move Xpressbees from new to reached_out in the deal view", Ava responded about the lead stage (Gregory Ipe already at reached_out) instead of the deal stage (Xpressbees deal still at new). She conflated the two entities because the system prompt only had a `LEADS` section with zero mention of deals.

## Root Cause
The `AGENT_SYSTEM_PROMPT_BASE` template in `server.py` (~line 4349) had:
```
LEADS ({lead_count} total):
{lead_details}
```
But no parallel `DEALS` section. Ava didn't know deals existed as a separate concept.

## Fix Applied

### 1. Template change (server.py)
After the `LEADS` section, added:
```
DEALS ({deal_count} total):
{deal_details}

Deals sit above leads in your pipeline. A deal can have multiple associated leads.
Deal stages mirror the most advanced lead stage:
new → reached_out → engaged → qualified → meeting_booked → deal_won | lost | dormant
When {owner_name} asks about moving something in the "deal view", they mean the DEAL stage, not the lead stage.
```

### 2. Query addition (~line 4804)
```python
deals = db.query(Deal).filter(Deal.tenant_id == tenant_id).all()
```

### 3. Deal details string (~line 4818)
```python
deal_details = "\n".join([
    f"- {d.org_name or 'Unknown'} | Stage: {d.stage or 'new'} | Value: ₹{d.expected_value or 0:,.0f} | Contact: {d.contact_name or '—'} | Source: {d.source_channel or '—'}"
    for d in deals
]) if deals else "No deals in the system yet."
```

### 4. Format call (~line 4867)
Added `deal_count=len(deals)` and `deal_details=deal_details` to `AGENT_SYSTEM_PROMPT_BASE.format()`.

## Related: Deal Stage Sync Fix
Also found that `_execute_cadence_action()` transitions `lead.stage = "reached_out"` on first outbound (~line 7010) without calling `_sync_deal_stage_from_lead()`. Added that call so the deal immediately mirrors the lead.

Same gap existed in `_handle_outbound_whatsapp()` (~line 7656) — already had an unconditional `_sync_deal_stage_from_lead()` after the commit, but added one inside the conditional block too for consistency.

## Verification
- Ask Ava about deal stages — she should now reference `DEALS (X total):` in her context
- Create a new lead with a deal → send first outbound → check deal stage changed to `reached_out`
