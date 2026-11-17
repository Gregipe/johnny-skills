# Deal-Lead Relationship Design (June 2026)

Design decisions from the session where Greg designed how deals and leads interact.

## Core Design

### Rule 1: Deal Creation on Lead Add

When a new lead is created with a company name or business email domain, and no deal exists for that company:

1. **Ava asks first:** "Bajaj Finance doesn't have a deal yet — should I create one?"
2. **Includes `[TOOL_CALL: create_deal]`** in the proposal (held for confirmation)
3. **On confirmation:** Deal is created with `org_name` matching the lead's company, `stage="new"`, and the lead is attached to it
4. **Personal domains (gmail.com, yahoo.com, etc.):** Skip the suggestion entirely

**Implementation:**
- `create_lead` tool executor emits `[SUGGEST_DEAL: org=..., domain=..., lead=..., lead_id=...]` marker in return value
- The re-call follow-up checks for `[SUGGEST_DEAL:` in `result_summary`
- If found, the re-call prompt tells the LLM: "Ask the user if they would like to create a deal. You MAY output [TOOL_CALL: create_deal]"
- The `_extract_domain()` function + `DOMAIN_BLOCKLIST` determine business vs personal email
- Existing deals are matched by `org_name` or `org_domain` before suggesting

### Rule 2: Stage Mirroring

**Single lead on a deal → deal matches that lead exactly (forward AND backward)**

If Gregory goes `new → reached_out → engaged → new`, the deal follows: `new → reached_out → engaged → new`.

**Multiple leads on a deal → deal = highest stage among all attached leads**

If ExpressBees has Gregory at `new`, Rajesh at `engaged`, and Priya at `meeting_booked`:
- Deal stage = `meeting_booked` (highest)
- Moving Gregory to `qualified` doesn't change the deal (already higher)
- Moving Priya back to `new` drops the deal to `engaged` (Rajesh is now highest)

**No stage cap** — The old code capped at `meeting_booked`. Removed. The deal should mirror the actual lead stage, not cap artificially.

### Rule 3: Sync Direction

The `_sync_deal_stage_from_lead()` function:
- Runs on EVERY lead stage change (not just forward moves)
- Queries ALL non-archived leads attached to the deal
- Calculates the highest stage index
- Only writes to the deal if the stage actually changes (prevents redundant event logging)
- Logs a `DealEvent` for every sync with description showing which leads contributed

## Implementation Notes

### The `_sync_deal_stage_from_lead` function (server.py ~line 7933)

```python
stage_order = ["new", "reached_out", "engaged", "qualified", "meeting_booked"]

# Find all non-archived leads attached to this deal
all_leads = db.query(Lead).filter(
    Lead.deal_id == deal.id,
    Lead.stage != "archived"
).all()

# Calculate highest stage among all attached leads
max_idx = -1
for l in all_leads:
    idx = stage_order.index(l.stage) if l.stage in stage_order else -1
    if idx > max_idx:
        max_idx = idx

if max_idx != deal_idx and max_idx >= 0:
    new_stage = stage_order[max_idx]
    # Update deal stage, log event
```

### The SUGGEST_DEAL Marker Pattern

The `create_lead` tool in `execute_tool()` checks after creating the lead:

```python
_suggest_deal = ""
_org_name = (lead.company or "").strip()
_org_domain = _extract_domain(lead.email or "")
if _org_name or _org_domain:
    # Check for existing deal by org_name or org_domain
    if not _existing_deal:
        _suggest_deal = f" [SUGGEST_DEAL: org={_deal_target}, domain=..., lead={lead.name}, lead_id={lead.id}]"
return _base + _suggest_deal
```

The follow-up construction intercepts this:
```python
if "[SUGGEST_DEAL:" in result_summary:
    # Parse the marker
    # Rewrite follow_up to ask user about deal creation
    # Tell LLM: "Ask if they want a deal. You MAY output [TOOL_CALL: create_deal]"
```

### ExpressBees Sync

On deploy, the ExpressBees deal was synced from `qualified` → `new` to match Gregory Ipe (the only attached lead, then at `new`). This was a one-time DB update + the new sync function handles all future changes.

## Testing

1. **New lead with company:** "Add Sahib Singh at Bajaj Finance" → Ava suggests deal for Bajaj Finance
2. **New lead with personal email:** "Add Dave at dave@gmail.com" → No deal suggestion
3. **Existing company:** Add another lead for Bajaj Finance → "This lead belongs to Bajaj Finance, which already has a deal" (auto-attach, no question)
4. **Single-lead mirroring:** Move Gregory `engaged → new` → ExpressBees deal follows to `new`
5. **Multi-lead highest:** Add Priya to ExpressBees at `meeting_booked` → deal stays at `meeting_booked` even if Gregory drops
