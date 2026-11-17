# ARA Deal Pipeline Design — Session Summary (May 22, 2026)

Complete design Q&A transcript for the deal pipeline feature.

## Design Decisions

### Q1: Lead-to-Deal Relationship
**Decision:** Organization-level deals. Multiple leads from the same org (same email domain) → one deal.
- Priya@acme.com + Rahul@acme.com = 1 deal "Acme"
- Procurement@acme.com joining later → same deal
- Future consideration: Different divisions within same org could be separate deals

### Q2: Deal Creation Trigger
**Decision:** Both manual + auto on qualification.
- **Dominant path:** Auto-create when a lead reaches `qualified` or `meeting_booked`
- **Manual fallback:** Human can create deal from Deals page
- **Definition of "qualified":** Lead matches ICP, logically interested, agrees to explore

### Q3: Pipeline Stages
**Decision:** Reachout → Qualified → Meeting Booked → Closed / Churned

| Stage | Definition |
|-------|-----------|
| **Reachout** | Attempting to converse / in conversation. Cold outbound starts here |
| **Qualified** | Lead matches ICP, interested in exploring. Inbound that showed interest starts here |
| **Meeting Booked** | Lead gave a slot for a demo/discussion with SDR or human |
| **Closed** | Sale completed (human marks) |
| **Churned** | Lost / dropped (human marks) |

- Inbound lead that booked a meeting → starts at `meeting_booked`
- Inbound lead that showed interest → starts at `reachout`
- Outbound cold lead → must start at `reachout`

### Q4: Deal Value
**Decision:** Human enters during discovery based on what the lead describes.
- Text input for ₹ amount
- Notes field for calculation (e.g. "200 users × ₹500/user = ₹1L annually")
- Always vetted by human initially

### Q5: Dashboard Metrics
**Decision:** Greg's SDR evaluation metric = Meetings Booked.

| Current | New |
|---------|-----|
| Total Leads | Total Leads |
| Leads Engaged | **Deals in Pipeline** |
| Meetings Booked | **Meetings Booked** |
| Revenue Closed | **Deals Closed** |

Revenue closed stat only meaningful when human marks a deal as Closed.

### Q6: Activities Scope
**Decision:** Both levels.
- **Lead-level:** Already exists in `showLeadDetail()` — one lead's conversation timeline
- **Deal-level:** Aggregated across all leads belonging to the deal's org
- **Global:** `/api/activities` — all conversations across all orgs, filterable by channel

### Q7: Domain Handling
- Auto-extract from `@domain.com` in lead email
- Blocklist for personal domains: gmail.com, yahoo.com, outlook.com, hotmail.com, icom
- Personal emails: human manually assigns deal via lead detail dropdown
- Phase 2: Auto-assign suggested by Ava via ActionItem

### Q8: Backfill
**Decision:** Forward-looking only. No scanning existing leads to create deals.

### Q9: Deal Detail Page
Contains:
- Pipeline stage + value card (Move Stage modal, Edit Value modal)
- List of all leads from org (clickable → lead detail)
- Aggregated activity timeline (DealEvent records + conversation previews)
- Stage change, value edit, lead attach/detach actions

### Q10: Ava's Role in Deal Assignment
**Decision:** Ava suggests → human confirms.
- Surface via ActionItem with `action_type="suggest_deal"`
- ActionItems show in Actions page + 🔔 badge in sidebar
- Phase 2: Auto-assign option from Actions page flashcard

## Implementation Notes

### Models Created
- `Deal`: id, tenant_id, org_name, org_domain, stage, expected_value, value_notes, created_at, updated_at
- `DealEvent`: id, deal_id, event_type, description, old_value, new_value, created_at
- `ActionItem`: id, tenant_id, action_type, title, description, ref_type, ref_id, status, created_at, resolved_at
- `Lead.deal_id`: FK added via ALTER TABLE

### API Endpoints Created
| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/deals | List all deals with lead count + last activity |
| GET | /api/deals/stats | Pipeline counts by stage |
| GET | /api/deals/{id} | Full deal detail + events + leads |
| POST | /api/deals | Create deal |
| PATCH | /api/deals/{id} | Update stage/value/notes (logs events) |
| POST | /api/deals/{id}/attach-lead | Attach lead to deal |
| POST | /api/deals/{id}/detach-lead | Detach lead from deal |
| GET | /api/activities | Aggregated conversation timeline |
| GET | /api/actions | Open action items |
| POST | /api/actions/{id}/resolve | Mark action resolved |
| POST | /api/actions/{id}/dismiss | Dismiss action |

### Frontend Pages Added
| Page | Function | Key Features |
|------|----------|-------------|
| Deals | `renderDeals()` | 5-column pipeline, stage counts, deal cards |
| Deal Detail | `showDealDetail()` | Info card, value, leads, event timeline, modals |
| Activities | `renderActivities()` | Aggregated timeline, channel filters |
| Actions | `renderActions()` | Action card list, resolve/dismiss, ref links |
| Dashboard | Updated `renderDashboard()` | New stat cards from `/api/deals/stats` |

### Sidebar
Active pages with onclick handlers: Home, Leads, Deals ✅, Activities ✅, Actions ✅, Integrations, Threads
Unused nav items (Companies, Inbox, Workflows, etc.) removed.

### Action Badge
Polls `/api/actions` every 15s. Shows red badge in sidebar when count > 0.
