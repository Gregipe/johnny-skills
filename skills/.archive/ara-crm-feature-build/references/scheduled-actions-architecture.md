# Scheduled Actions System — Full Implementation

## Context

Built as part of the ARA Learning Flywheel Phases 4-5. Enables Ava to schedule follow-up actions when leads say "call me later" or "send an email on Monday," with automatic execution and retry logic.

## Files Modified

- `/Users/greg/ara/database.py` — Added `ScheduledAction` SQLAlchemy model
- `/Users/greg/ara/server.py` — Scheduler daemon, 7 API endpoints, auto-cancellation, Ava prompt
- `/Users/greg/ara/dashboard_template.py` — Actions page UI, bell filtering

## Architecture

```
Ava detects "call me later" intent
  → POST /api/actions (creates ScheduledAction row, status=pending)
  → Background scheduler daemon polls every 30s
  → When scheduled_at <= now: marks "firing", executes action
  → On success: "completed" + fired_at
  → On failure: retry_count++, exponential backoff (60s→300s→900s)
  → On perm failure: LearningNotification to Greg
```

## State Machine

```
pending → firing → completed ✓
pending → firing → failed → (retry) → firing → completed ✓
pending → firing → failed → (max retries) → failed [perm]
pending → cancelled (when lead re-engages)
firing → cancelled (edge case: lead messages during execution)
```

## Key Implementation Details

### 1. Scheduler Daemon (server.py)

```python
def _run_scheduler():
    logger = logging.getLogger("scheduler")
    while True:
        try:
            db = init_session()
            try:
                now = utcnow()
                # Due actions
                due = db.query(ScheduledAction).filter(
                    ScheduledAction.tenant_id == TENANT_ID,
                    ScheduledAction.status.in_(["pending", "firing"]),
                    ScheduledAction.scheduled_at <= now,
                ).all()
                # Retry-eligible
                retry = db.query(ScheduledAction).filter(
                    ScheduledAction.tenant_id == TENANT_ID,
                    ScheduledAction.status == "failed",
                    ScheduledAction.next_retry_at != None,
                    ScheduledAction.next_retry_at <= now,
                    ScheduledAction.retry_count < ScheduledAction.max_retries,
                ).all()
                for action in due + retry:
                    action.status = "firing"
                    db.commit()
                    success = _execute_action(action, db)
                    if success:
                        action.status = "completed"
                        action.fired_at = utcnow()
                    else:
                        action.retry_count = (action.retry_count or 0) + 1
                        if action.retry_count >= action.max_retries:
                            action.status = "failed"
                        else:
                            action.status = "failed"
                            backoff = [60, 300, 900][min(action.retry_count - 1, 2)]
                            action.next_retry_at = utcnow() + timedelta(seconds=backoff)
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")
        time.sleep(30)
```

### 2. Execution Channels

```python
def _execute_action(action, db):
    lead = db.query(Lead).filter(Lead.id == action.lead_id).first()
    if not lead: return False
    try:
        if action.action_type == "whatsapp":
            wa.send(lead.phone, action.payload.get("message", ""))
        elif action.action_type == "email":
            send_via_gmail_api(lead.email, action.payload.get("subject", ""), action.payload.get("body", ""))
        elif action.action_type == "call_reminder":
            # Create LearningNotification for Greg
            notif = LearningNotification(tenant_id=action.tenant_id, notif_type="call_reminder",
                title=f"📞 Call reminder: {lead.name}", message=action.payload.get("message", ""),
                lead_id=action.lead_id)
            db.add(notif); db.commit()
        elif action.action_type == "internal_note":
            notif = LearningNotification(tenant_id=action.tenant_id, notif_type="internal_note",
                title=f"📌 Note: {lead.name}", message=action.payload.get("message", ""),
                lead_id=action.lead_id)
            db.add(notif); db.commit()
        return True
    except Exception as e:
        action.last_error = str(e)
        db.commit()
        return False
```

### 3. Auto-Cancellation (in WhatsApp handler)

After parsing inbound message and before Ava responds:

```python
pending = db.query(ScheduledAction).filter(
    ScheduledAction.tenant_id == tenant_id,
    ScheduledAction.lead_id == lead.id,
    ScheduledAction.status.in_(["pending", "firing"]),
).all()
for pa in pending:
    pa.status = "cancelled"
db.commit()
# The context passed to Ava includes: "Cancelled X pending actions for this lead."
```

### 4. API Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/api/actions` | Create action (Ava calls this) |
| GET | `/api/actions` | List with ?status, ?lead_id, ?upcoming=true filters |
| GET | `/api/actions/stats` | {upcoming, pending_now, completed_today, failed} — MUST be before /{id} |
| GET | `/api/actions/{id}` | Detail |
| PATCH | `/api/actions/{id}` | Update/reschedule |
| POST | `/api/actions/{id}/cancel` | Cancel one |
| POST | `/api/actions/cancel-for-lead/{id}` | Cancel all pending for lead |

### 5. Actions Page UI (Dashboard)

**Stats cards** — 4-column grid:
- Upcoming count (yellow accent)
- Pending/Due now count (blue accent)
- Completed today (green accent)
- Failed count (red accent, only shown if >0)

**Timeline cards** — grouped by day:
- Today / Tomorrow / "May 26" headers
- Each card: type icon (💬📧📞📌), message preview, lead name (clickable → lead detail), time (relative or absolute), status badge (colored), cancel button
- Loading spinner while fetching
- Empty state when no actions

### 6. Notification Bell Filtering

**Show in bell (AHA-only):** `synthesis_ready`, `action_failed`, `call_reminder`, `internal_note`, `action_scheduled`
**Hide from bell (noisy):** `new_skill`, `coaching_response`, `needs_review`

```javascript
// Bell fetch uses types filter
fetch('/api/learning/notifications?acknowledged=false&types=synthesis_ready,action_failed,call_reminder,internal_note,action_scheduled')
// Learning page Activity tab fetches without filter
fetch('/api/learning/notifications?acknowledged=false')
```

### 7. Ava System Prompt Instructions

Added to Ava's instructions:
- Detect "call me later", "follow up next week", "send an email on Monday" intent
- Confirm the time with the lead if vague
- Call POST /api/actions with lead_id, action_type, channel, payload, scheduled_at
- Always use the same channel unless lead specifies otherwise
- Auto-cancellation happens automatically on re-engagement

## Pitfalls Encountered

- **Route ordering:** `/api/actions/stats` MUST be before `/api/actions/{id}` in FastAPI or "stats" is treated as an action_id
- **ImportError:** `dateutil.parser` not in stdlib — use `datetime.fromisoformat()` instead
- **Thread safety:** Scheduler daemon creates its own DB session per tick — reused sessions across ticks go stale
- **LearningNotification model:** Check column names match existing schema before referencing them in queries
- **Pydantic schemas:** Create a `ScheduledActionCreate` model or use generic dict — don't couple to the SQLAlchemy model directly
