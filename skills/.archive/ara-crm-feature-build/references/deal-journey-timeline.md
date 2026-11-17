# Deal Journey Timeline

A horizontal pipeline component showing deal stage progression, time-in-stage per segment, and visual completed/current/future states with hover tooltips.

## Architecture

### Data Model

The `Deal` model needs a `stage_entered_at` column to track when the current stage was entered:

```python
stage_entered_at = Column(DateTime)  # set on create + each stage change
```

**Migration** (SQLite — ALTER TABLE):
```python
from sqlalchemy import inspect, text as sa_text
inspector = inspect(db_session.get_bind())
cols = [c['name'] for c in inspector.get_columns('deals')]
if 'stage_entered_at' not in cols:
    db_session.execute(sa_text("ALTER TABLE deals ADD COLUMN stage_entered_at DATETIME"))
    db_session.commit()
db_session.execute(sa_text("UPDATE deals SET stage_entered_at = created_at WHERE stage_entered_at IS NULL"))
db_session.commit()
```

**Set on:**
- **Create**: `stage_entered_at=utcnow()`
- **Stage change (PATCH)**: `d.stage_entered_at = utcnow()`

### Stage Timeline Computation

`_compute_stage_timeline(deal, db)` builds a **full 5-stage pipeline** (Reachout → Qualified → Meeting Booked → Closed Won → Churned) for every deal. ALL 5 stages always show, regardless of whether the deal has visited them:

1. Walk DealEvent stage_change events chronologically to build a `stage → {entered_at, exited_at}` map
2. Prefer `deal.stage_entered_at` for the current stage's entered time (more accurate than last event timestamp)
3. Create the final timeline by iterating through all 5 stages:
   - If a stage has event data: use real entered/exited timestamps, compute real duration
   - If a stage was never visited: `entered_at: null, exited_at: null, duration_seconds: 0`
   - `is_completed = stage_index < current_stage_index` — stages before current are green
   - `is_current = stage == deal.stage`

This means a deal at "Meeting Booked" shows:
- **Reachout**: green (completed, has real data)
- **Qualified**: green (completed, `entered_at: null, duration: —` if skipped through)
- **Meeting Booked**: green + highlight (current, live timer from stage_entered_at)
- **Closed Won**: gray (future, no data)
- **Churned**: gray (future, no data)

Timeline entry shape:
```python
{
    'stage': 'meeting_booked',
    'stage_label': 'Meeting Booked',
    'entered_at': ISO timestamp or None,
    'exited_at': ISO timestamp or None,  # None for current stage
    'duration_seconds': 119095,
    'is_current': True,
    'is_completed': True,
}
```

## Frontend

### Duration Formatter
Returns readable string from seconds: `< 1 min` → `12 min` → `3h 15m` → `5d 8h` → `2mo 3d` → `—` (for 0/negative).

### Timeline Renderer
- Iterates timeline array, assigns CSS class per `is_current`/`is_completed`
- Tooltip: `position: absolute; bottom: calc(100% + 10px)` — hover on `timeline-block` shows/hides tooltip via CSS only (no JS)
- Arrow connectors: CSS border triangles between blocks, color matches preceding block
- Last segment: no arrow, fully rounded corners
- After timeline: "Current Stage: X" label + stuck warning if > 14 days

### CSS Colors
- **Completed**: green gradient `#059669 → #10b981`
- **Current**: same green gradient as completed, distinguished via `box-shadow: 0 0 0 2px rgba(5,150,105,0.4), 0 2px 12px rgba(5,150,105,0.3)` + `transform: scale(1.04)` + `z-index: 2`. Not a different color — uses shadow+scale for prominence while keeping the green series continuous.
- **Future**: gray `#F3F4F6` with `#9A9A9E` text
- **Arrow connector**: `.timeline-arrow` uses `border-left-color` matching the preceding segment's color. Green for completed+current, gray for future. Last segment gets no arrow.
- **Tooltip**: dark `#1a1a2e` with `::after` triangle pointing down

### Current Stage Label (below timeline)
- Text: `Current Stage: X` — stage name in green `#059669` with `font-weight: 700`
- Stuck warning: Yellow banner (`#FEF3C7` bg, `#92400E` text) when duration > 14 days

### Placement
Right after the deal header breadcrumb + action buttons, before the deal info card. Replaces the old inline Status section.
