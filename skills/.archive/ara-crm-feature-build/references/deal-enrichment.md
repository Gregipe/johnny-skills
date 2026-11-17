# Deal Enrichment Implementation (May 2026)

## Fields Added

| Field | Type | Default |
|-------|------|---------|
| `contact_name` | String | "" |
| `contact_email` | String | "" |
| `contact_designation` | String | "" |
| `contact_phone` | String | "" |
| `industry_segment` | String | "" (dropdown: 15 options) |
| `source_channel` | String | "" (dropdown: 9 options + Other) |
| `deal_owner` | String | "Ava" |

## Industry Segments

Technology/SaaS, Manufacturing, Healthcare, Financial Services, E-commerce/Retail, Education, Real Estate, Logistics/Supply Chain, Media/Entertainment, Professional Services, Telecom, Energy/Utilities, Staffing and Recruiting, Pharma, Other

## Source Channels

LinkedIn, Website, Referral, WhatsApp, Email, Event, Cold Call, Partner, Other

## Lead Auto-Creation Flow

1. On POST `/api/deals`, if `contact_phone` or `contact_email` is provided:
   - Phone lookup → Email lookup → Create new lead
   - New lead gets: name, email, phone, company=org_name, lead_source=source_channel or "deal", stage="new", deal_id=deal.id
   - Existing matched lead (without a deal_id) gets linked via `lead.deal_id = deal.id`
2. DealEvent created for lead attachment
3. Serialized deal includes `leads[]` array with id, name, email, phone, stage

## Edit Modal Layout

The Edit modal uses a 2-column row layout:
- Row 1: Org Name (full width)
- Row 2: Contact Name | Designation
- Row 3: Email | Phone
- Row 4: Stage (dropdown) | Industry (dropdown)
- Row 5: Source (dropdown) | Owner
- Row 6: Expected Value (number)
- Row 7: Notes (textarea)
- Row 8: Save | Cancel

## Deal Detail Page Sections

- **Contact Person**: name, designation, email (blue), phone
- **Expected Value**: formatted in ₹, notes below
- **Details**: Industry, Source, Owner, Domain (lead-info-row pattern)
- **Leads (N)**: clickable list linking to lead detail

## Add Deal Modal (modal, not inline form)

The "+ Add Deal" button in column headers now opens a modal (`showAddDealModal(stage)`) instead of revealing an inline form. The modal has the same fields as Edit, with Stage pre-filled to the column clicked from. This replaced the old approach after user feedback that inline was "ugly."

The `add-deal` data-action handler was simplified from a 3-state inline form reveal to a single call:

```javascript
// Before: inline form toggle (old approach)
// Show inline form, hide button
if (action === 'add-deal') { /* showForm */ return; }
if (action === 'cancel-add-deal') { /* hideForm */ return; }
if (action === 'submit-add-deal') { /* post data */ return; }

// After: modal approach
if (action === 'add-deal') { showAddDealModal(t.dataset.stage); return; }
```
No more `cancel-add-deal` or `submit-add-deal` handlers needed in delegation.

## Button Audit: Actions Found Broken

| Screen | Issue | Fix |
|--------|-------|-----|
| Deals pipeline | Deal cards not clickable | `e.target.closest('.deal-card')` |
| Stage change modal | Cancel button dead | Direct event listener on overlay |
| Value edit modal | Cancel button dead | Direct event listener on overlay |
| Lead detail | Dead "More" button | Removed dead element |
| Learnings | "+N more" collapsed categories | Created handler, stores data in cache |

## Mandatory Fields on Create

- `org_name` (required — validated both client-side and server-side)
- `stage` (required — validated server-side; must be one of the 5 pipeline stages)

## Files Changed

- `/Users/greg/ara/database.py` — Deal model: 7 new columns
- `/Users/greg/ara/server.py` — migration, serialize, create, update endpoints
- `/Users/greg/ara/static/dashboard.js` — renderDeals, showDealDetail, editDeal, saveDeal, submit-add-deal
- `/Users/greg/ara/dashboard_template.py` — (no changes needed, all JS in static file now)
