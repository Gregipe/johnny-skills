# Engagement Stage Implementation (May 2026)

## DB Changes

Added two columns to `Lead` model in `database.py`:

```python
last_contacted_at = Column(DateTime, nullable=True)
first_reply_at = Column(DateTime, nullable=True)
```

Migration in `server.py` lifespan:

```python
lead_migrations = {
    'last_contacted_at': "ALTER TABLE leads ADD COLUMN last_contacted_at DATETIME",
    'first_reply_at': "ALTER TABLE leads ADD COLUMN first_reply_at DATETIME",
}
```

## Inbound Handler Wiring (`_handle_inbound_whatsapp`, ~line 3960)

```python
now_dt = utcnow()
lead.last_contacted_at = now_dt
if not lead.first_reply_at:
    lead.first_reply_at = now_dt
```

Placed right before the stage-transition check (`if lead.stage in ("new", "contacted"): lead.stage = "engaged"`).

## API Exposure

Both in `list_leads` (line ~424) and single lead endpoint (line ~539):

```python
"last_contacted_at": l.last_contacted_at.isoformat() if l.last_contacted_at else None,
"first_reply_at": l.first_reply_at.isoformat() if l.first_reply_at else None,
```

## Prompt Injection

### agent_chat() (~line 2216)

```python
def _engagement_stage(l):
    if not l.first_reply_at:
        return "outbound"
    if not l.last_contacted_at or l.last_contacted_at == l.first_reply_at:
        return "first_reply"
    days_since = (utcnow() - l.last_contacted_at).days if l.last_contacted_at else 7
    return "repeat_contact" if days_since > 7 else "follow_up"

lead_details = "\n".join([
    f"- {l.name} | ... | Engagement: {_engagement_stage(l)} | Email: ..."
    for l in leads
])
```

Plus tone guidance in `AGENT_SYSTEM_PROMPT_BASE` (~line 2095):

```
Each lead has an Engagement signal: outbound / first_reply / follow_up / repeat_contact.
Adjust your tone:
- first_reply: Be more deferential
- follow_up: Direct and efficient
- repeat_contact: Warm re-engagement
- outbound: Standard SDR outreach
```

### AVA_AUTO_SYSTEM_PROMPT (~line 4025)

```python
def _eng_stage(l):
    # same logic
engagement = _eng_stage(lead)
prompt = AVA_AUTO_SYSTEM_PROMPT.format(
    lead_engagement=engagement,
    ...
)
```

## Key Lines in server.py

| What | Line range |
|------|-----------|
| DB migration (ALTER TABLE) | ~161-166 |
| Lead model columns | database.py:68-69 |
| Inbound handler (set both) | ~3960-3964 |
| list_leads API exposure | ~424-425 |
| Single lead API exposure | ~539-540 |
| _engagement_stage() + lead_details | ~2216-2226 |
| Engagement tone guidance in prompt | ~2095-2100 |
| AVA_AUTO_SYSTEM_PROMPT format | ~4025-4038 |
| AVA_AUTO_SYSTEM_PROMPT template | ~3558 (Engagement: {lead_engagement} + tone) |
