# ARA Email Pipeline Notes (Archived)

> This file contains consolidated notes from the archived `ara-email-pipeline` skill. The main skill is `ara-email-integration`.

## Overview

The inbound email pipeline detects lead replies via Gmail API OAuth polling.

## Architecture

```
Lead replies to Ava's email → Gmail inbox
    ↓ (polled every 60s by scheduler)
_poll_inbound_gmail(db)
    ├── Lists unread messages via Gmail API
    ├── Matches sender email to leads (Lead.email ILIKE)
    ├── Extracts body text (plain text preferred, HTML fallback)
    ├── Creates Conversation(lead_id, channel="email", direction="inbound")
    ├── Stage transition: new/reached_out → engaged
    ├── Syncs deal stage via _sync_deal_stage_from_lead()
    ├── Cancels pending cadence actions for engaged lead
    └── Marks email as read in Gmail
```

## Code Location

| Function | File | Line |
|----------|------|------|
| `_poll_inbound_gmail(db)` | server.py | ~7855 |
| `_extract_gmail_body(msg)` | server.py | ~7820 |
| `refresh_gmail_token(config)` | email_utils.py | ~181 |
| Scheduler integration | server.py | ~8187 |

## Stage Transition

```python
if lead.stage in ("new", "reached_out"):
    lead.stage = "engaged"
    lead.lead_source = "email"
    lead.last_contacted_at = utcnow()
    lead.first_reply_at = utcnow()
    _sync_deal_stage_from_lead(lead.id)
```

## Cadence Cancellation

After engagement, cancels any pending outbound actions:

```python
pending = db.query(ScheduledAction).filter(
    ScheduledAction.lead_id == lead.id,
    ScheduledAction.status.in_(["pending", "firing"]),
).all()
for pa in pending:
    pa.status = "cancelled"
```

## Key Differences from ara-email-integration

- `ara-email-integration` is the primary skill with full OAuth setup
- This pipeline was the inbound-only component
- Both now consolidated into `ara-email-integration`