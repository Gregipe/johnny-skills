# Pipeline Stage Refactor — Complete Workflow

When rewiring pipeline stages (lead or deal), follow this sequence to catch every reference.

## 1. Define New Stages

### Lead Pipeline (6 stages)
```
new → reached_out → engaged → qualified → meeting_booked → dormant
```
Dropped: `contacted`, `proposal`, `closed_won`, `closed_lost`

### Deal Pipeline (8 stages)
```
new → reached_out → engaged → qualified → meeting_booked → deal_won → lost → dormant
```
Dropped: `reachout`, `closed`, `churned`

## 2. DB Model (database.py)

Update the `stage` column comment on both `Lead` and `Deal` models. Change defaults:
- Lead: `default="new"` (unchanged)
- Deal: `default="new"` (was `"reachout"`)

## 3. Migration (server.py lifespan)

Add before the final `db_session.commit()` near the end of migrations:

```python
db_session.execute(sa_text("UPDATE leads SET stage='reached_out' WHERE stage='contacted'"))
db_session.execute(sa_text("UPDATE leads SET stage='meeting_booked' WHERE stage='proposal'"))
db_session.execute(sa_text("UPDATE leads SET stage='dormant' WHERE stage='closed_won'"))
db_session.execute(sa_text("UPDATE leads SET stage='dormant' WHERE stage='closed_lost'"))
db_session.execute(sa_text("UPDATE deals SET stage='deal_won' WHERE stage='closed'"))
db_session.execute(sa_text("UPDATE deals SET stage='lost' WHERE stage='churned'"))
db_session.execute(sa_text("UPDATE deals SET stage='new' WHERE stage='reachout'"))
```

## 4. Server.py — All Stage String References

Search for old stage strings across the full codebase:

```bash
grep -n '"reachout"\|"contacted"\|"proposal"\|"closed_won"\|"closed_lost"\|"churned"' server.py
```

Targets to update:
- Stage transition hooks: inbound handler (`"contacted" → "reached_out"`), outbound handler (`"new" → "reached_out"`, `"contacted" → "reached_out"`)
- Cadence scheduling check: which stages skip scheduling
- Deal creation defaults: `stage="reachout"` → `stage="new"`
- `_compute_stage_timeline()`: stage_labels dict, stages list, comment line
- `_serialize_deal()`: the inline `.get(d.stage, d.stage)` dict
- `deal_stats()`: `"closed"` → `"deal_won"`, rename response key
- CSV lead scheduling query: `Lead.stage.in_(["new", "contacted"])` → `["new", "reached_out"]`
- Agent suggestions: `stage_hint in ("new", "contacted")` → `("new", "reached_out")`

## 5. Dashboard.js — All Stage String References

```bash
grep -n '"reachout"\|"contacted"\|"proposal"\|"closed_won"\|"closed_lost"\|"churned"' static/dashboard.js
```

Targets:
- `renderDeals()`: stages array, stageLabels dict, pipeline vs terminal stage split
- `editDeal()`: stages + labels for dropdown
- `showAddDealModal()`: stages + labels for dropdown
- Lead stage inline edit: stages array for `<select>`
- Homepage stats: `stats.closed` → `stats.deal_won`

## 6. Auto-Dormant Pattern

Use the `_check_dormant()` function pattern:
- Runs every 30s in the scheduler loop
- Queries leads with stage NOT "dormant"
- For each: find most recent `Conversation` by `lead_id`, check if `created_at < cutoff (30 days)`
- If no conversation at all: check `lead.created_at < cutoff`
- Deals: if all attached leads dormant → deal dormant; or if no leads and `updated_at < cutoff`
- Dormant leads who reply go to "engaged" (add "dormant" to the stage list in inbound handler)

## 7. Deal Stage Auto-Sync

Use the `_sync_deal_stage_from_lead(lead_id)` function pattern:
- Called after any lead stage change (inbound, outbound, PATCH)
- Read lead's deal_id, get deal
- Stage order: `["new", "reached_out", "engaged", "qualified", "meeting_booked"]`
- Only moves deal forward (never backward), caps at meeting_booked
- Creates DealEvent for audit trail
- Post-meeting_booked: manual moves only (via drag-drop or PATCH)
