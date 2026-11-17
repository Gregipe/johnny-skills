# Lead Industry Inheritance & Deal Sync

## Lead Model Has No `industry` Column

The Lead model (`database.py`) has:
- `segment` — broad bucket: logistics, bfsi, qsr, ecommerce
- `product_interest` — what product/capability they're interested in
- `deal_id` → `deal` relationship to the Deal model

The Deal model has `industry_segment` — free-text field (e.g. "Logistics/Supply Chain", "Technology/SaaS").

## Cadence Message Generation — Industry Resolution

File: `/opt/ara/app/services/cadence.py`, function `generate_step_message()`, line ~254.

The function builds lead context for the LLM prompt. **The correct hierarchy:**

```python
Industry: {lead.deal.industry_segment if lead.deal and lead.deal.industry_segment 
           else lead.product_interest or "Not specified"}
```

**Pitfall — `lead.industry` does not exist:**
```python
# CRASHES: AttributeError: 'Lead' object has no attribute 'industry'
Industry: {lead.product_interest or lead.industry or 'Not specified'}
```

This crash silently kills cadence email generation. The scheduler retries 3x then permanently fails the action. The lead's pending actions all show as `failed` or `pending` with no clear error surfaced to the user.

## Domain-to-Deal Auto-Matching

File: `/opt/ara/server.py`, line ~1295 (lead creation/stage-change path).

`extract_domain()` in `app/config.py` strips the domain from the lead's email and matches against `Deal.org_domain`. If a match exists, the lead is auto-attached to the deal. The lead inherits the deal's `industry_segment` for cadence messaging.

`DOMAIN_BLOCKLIST` filters Gmail, Yahoo, Outlook, etc. — no deal match → industry falls through to "Not specified" → LLM uses generic messaging posture from the cadence template.

## `_sync_deal_stage_from_lead` — Silent Failure Trap

File: `/opt/ara/server.py`, function `_sync_deal_stage_from_lead()`.

**Original code:**
```python
    except Exception:
        pass
```

This silently swallowed ALL errors. Deals would drift out of sync with leads with zero visibility. The function is called from 13 code paths after every lead stage change.

**Fix:**
```python
    except Exception as e:
        import logging
        logging.getLogger("scheduler").warning(
            f"_sync_deal_stage_from_lead failed: {e}"
        )
```

**How it works:** After any lead stage change, queries all non-archived leads attached to the same deal, finds the highest stage in `["new", "reached_out", "engaged", "qualified", "meeting_booked"]`, and syncs the deal to match. Works forward AND backward — if all leads drop to "new", the deal follows.

## Deal `industry_segment` Required for Manual Creation

File: `/opt/ara/server.py`, `create_deal` handler.

```python
if not deal.industry_segment:
    return {"error": "industry_segment is required"}
```

Auto-creation (lead stage change → deal auto-creation) allows empty `industry_segment` — won't block existing flows.

## Manual Sync

When a deal has drifted out of sync, manually invoke:
```python
from server import _sync_deal_stage_from_lead
from database import init_db, Lead
db = init_db()
lead = db.query(Lead).filter(Lead.name.ilike('%Name%')).first()
_sync_deal_stage_from_lead(lead.id)
db.close()
```
