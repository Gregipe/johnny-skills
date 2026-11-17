# Lead Industry Resolution for Cadence Generation

## The Bug

`generate_step_message()` in `app/services/cadence.py:254` references `lead.industry`:

```python
lead_context = f"""Lead: {lead.name or 'Unknown'}
Company: {lead.company or 'Unknown'}
Industry: {lead.product_interest or lead.industry or 'Not specified'}
```

`Lead` model has NO `industry` attribute → `AttributeError: 'Lead' object has no attribute 'industry'`

## The Fix

Resolve industry through the lead's deal relationship:

```python
Industry: {lead.product_interest or (lead.deal.industry_segment if lead.deal else None) or 'Not specified'}
```

## Model Field Mapping

| Model | Industry-relevant fields | Notes |
|-------|------------------------|-------|
| `Lead` | `segment` (logistics/bfsi/qsr/ecommerce), `product_interest`, `deal_id` | No `industry` column |
| `Deal` | `industry_segment` (e.g. "Technology/SaaS"), `org_domain` | Industry lives here |

## Auto-Attachment via Domain

When a lead is created with a company domain email (e.g. `greg@xpressbees.com`):

1. `extract_domain()` in `app/config.py` strips the domain
2. `DOMAIN_BLOCKLIST` filters out gmail/yahoo/hotmail etc. — these don't trigger matching
3. Server searches for existing `Deal` with matching `org_domain`
4. If found: lead is auto-attached (`lead.deal_id = deal.id`)
5. If not found: new deal is created (but `industry_segment` defaults to `""`)

This logic runs in `server.py` ~line 1295 at lead creation and stage-change time.

## No-Deal Fallback

Leads with no deal (gmail/yahoo domain → no match, no deal created):
- `lead.deal` is `None`
- Industry resolves to `'Not specified'`
- LLM prompt handles this with generic messaging — no sector-specific pain points
