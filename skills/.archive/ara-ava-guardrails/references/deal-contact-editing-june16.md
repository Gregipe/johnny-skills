# Deal Contact Editing — June 16, 2026

## Problem
Greg wanted to edit a deal and add a primary contact from the leads. Ava had `update_deal` but the tool description only mentioned `stage` and `expected_value`. She didn't know `lead_id` was supported.

## Solution: Tool Description + Auto-Sync

### 1. Tool Description Updated
```python
"update_deal": {
    "description": "-- Update deal fields. Args: {deal_name, fields: {stage, expected_value, lead_id, contact_name, value_notes}}. 
    To attach a lead as primary contact, set lead_id to the lead's ID."
}
```

### 2. Auto-Sync When lead_id Is Set (server.py ~line 3599)
When `lead_id` is included in `fields`, the handler auto-populates `contact_name`, `contact_email`, `contact_phone` from the lead:
```python
if "lead_id" in fields and fields["lead_id"]:
    _contact = db.query(Lead).filter(Lead.id == fields["lead_id"]).first()
    if _contact:
        deal.contact_name = _contact.name
        deal.contact_email = _contact.email
        deal.contact_phone = _contact.phone
        deal.contact_designation = getattr(_contact, 'designation', None)
```

### 3. Deal Model Fields (database.py)
```python
contact_name = Column(String)    # primary contact person name (synced from lead)
contact_email = Column(String)   # primary contact email (synced from lead)
contact_phone = Column(String)   # primary contact phone (synced from lead)
lead_id = Column(String, ForeignKey("leads.id"))  # primary contact lead
```

### Verification
```
"set Ajay Fageria as the primary contact for Shriram Finance"
  → get_lead_detail: Ajay Fageria, Company: Shriram Finance, Phone: 1111111116
  → update_deal(deal_name="Shriram Finance", fields={"lead_id": "9bbdcc7d"})
  → DB: contact_name=Ajay Fageria, contact_phone=1111111116
  → Response: "✅ Done. Ajay Fageria is now the primary contact on the Shriram Finance deal"
```

### Alternative Path
If the deal doesn't exist yet, Ava uses `create_deal` + `attach_to_deal`:
```
"attach Vinay Bhoj as the primary contact for the Magic Billion deal"
  → search_deals: not found
  → get_lead_detail: Vinay Bhoj, Company: Magic Billion
  → create_deal(org_name="Magic Billion")
  → attach_to_deal(lead_name="Vinay Bhoj", deal_name="Magic Billion")
```

### Also Available
- `attach_to_deal`: Links a lead to a deal (sets `Lead.deal_id`)
- `update_deal` with `lead_id`: Sets the primary contact on the deal (auto-syncs details)
