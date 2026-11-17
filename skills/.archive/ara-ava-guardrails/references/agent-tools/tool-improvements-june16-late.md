# Tool Improvements — June 16, 2026 (Late Session)

## `attach_to_deal` — Auto-Set Primary Contact

**Problem:** `attach_to_deal` only set `lead.deal_id` (linking lead to deal). It never set `deal.lead_id` (deal's primary contact) or synced `contact_name/email/phone`. When Greg asked "attach Vinay as primary contact," the lead was linked but the deal showed no contact.

**Fix:** When the deal has no primary contact (`deal.lead_id` is NULL), `attach_to_deal` now auto-sets:
```python
if not deal.lead_id:
    deal.lead_id = lead.id
    deal.contact_name = lead.name
    deal.contact_email = lead.email
    deal.contact_phone = lead.phone
    deal.contact_designation = getattr(lead, 'designation', None)
```

Response includes `(primary contact)` tag when this auto-set fires.

**Location:** server.py ~line 3482, `elif tool_name == "attach_to_deal"`

## `create_deal` — Duplicate org_name Check

**Problem:** `create_deal` had no duplicate detection. Voice notes and multi-step flows could create duplicate deals (e.g., two "Shriram Finance" deals). The LLM then got confused about which one to use.

**Fix:** Check for existing deal with same `org_name` before creating:
```python
existing = db.query(Deal).filter(
    Deal.tenant_id == tenant_id,
    Deal.org_name == org_name
).first()
if existing:
    return f"Deal '{org_name}' already exists (id={existing.id[:8]}, stage={existing.stage}). 
    Use update_deal to modify it, or attach_to_deal to add contacts."
```

**Location:** server.py ~line 3506, `elif tool_name == "create_deal"`

## `update_deal` — `lead_id` Support with Auto-Sync

**Problem:** `update_deal` tool description only mentioned `stage` and `expected_value`. The LLM didn't know it could set `lead_id` to attach a primary contact.

**Fix:** Tool description updated to include `lead_id` and `contact_name` in the example:
```
Args: {"deal_name": "...", "fields": {"lead_id": "abc123", "contact_name": "...", ...}}
```

When `lead_id` is set, contact details auto-sync from the lead:
```python
if "lead_id" in fields and fields["lead_id"]:
    _contact = db.query(Lead).filter(Lead.id == fields["lead_id"]).first()
    if _contact:
        deal.contact_name = _contact.name
        deal.contact_email = _contact.email
        deal.contact_phone = _contact.phone
```

**Location:** server.py ~line 3588, TOOL_SCHEMAS around line 5540

## `_build_pending_description` — Added `attach_to_deal` Case

**Problem:** The pending description builder had no handler for `attach_to_deal` tool calls. Multi-step proposals showed only "💰 Create deal" even when attachment was also queued.

**Fix:** Added case:
```python
elif name == "attach_to_deal":
    parts.append(f"🔗 Attach {args.get('lead_name', 'lead')} to deal {args.get('deal_name', '')} — shall I attach?")
```

**Location:** server.py ~line 5983, `_build_pending_description()`
