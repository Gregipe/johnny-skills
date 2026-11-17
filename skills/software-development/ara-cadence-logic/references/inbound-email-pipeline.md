# Inbound Email Pipeline (Gmail API)

## Architecture

The email poller runs inside `_run_scheduler()` every 60s (throttled internally). It polls the connected Gmail inbox via Gmail API for unread replies from known leads. When a matched reply is found, it follows the same stage-transition pattern as the WhatsApp inbound handler.

## Flow

```
Scheduler (30s loop)
    └── _poll_inbound_gmail(db)  ← every 60s, throttled by _EMAIL_POLL_LAST
            │
            ├── 1. Get OAuth config from integration_config (email-gmail)
            ├── 2. Refresh token via refresh_gmail_token() if stale
            ├── 3. GET /messages?q=is:unread&maxResults=20 (list)
            ├── 4. For each message:
            │       ├── GET /messages/{id}?format=metadata&metadataHeaders=From,Subject
            │       ├── Extract sender email from From header
            │       ├── Skip if sender == connected email (self-reply guard)
            │       ├── Match sender to Lead.email (ILIKE)
            │       ├── GET /messages/{id}?format=full (body)
            │       ├── Create Conversation (channel=email, direction=inbound)
            │       ├── Stage transition: new/reached_out → engaged
            │       ├── lead.last_contacted_at, lead.first_reply_at set
            │       ├── lead.lead_source = "email"
            │       ├── _sync_deal_stage_from_lead(lead.id)
            │       ├── Cancel pending cadence ScheduledActions
            │       └── POST /messages/{id}/modify (mark as read)
            └── Unknown senders: marked as read (no re-processing)
```

## Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `refresh_gmail_token(config)` | `email_utils.py:181` | Refresh OAuth access token via Google's token endpoint |
| `_extract_gmail_body(msg)` | `server.py:~7820` | Extract plain text / HTML body from Gmail API message |
| `_poll_inbound_gmail(db)` | `server.py:~7855` | Main poller — list, match, process, mark read |
| `_EMAIL_POLL_LAST` | server.py module-level | 60s throttle timestamp |

## Stage Transition (matches WhatsApp inbound handler)

```
if lead.stage in ("new", "reached_out"):
    lead.stage = "engaged"
    lead.lead_source = "email"
    _sync_deal_stage_from_lead(lead.id)
    # Cancel pending cadence actions
```

## Prerequisites

1. Gmail OAuth configured via `integration_config` (integration_id=`email-gmail`)
2. Valid `client_id`, `client_secret`, `access_token`, `refresh_token`
3. `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` env vars for fallback
4. Redirect URI in Google Cloud Console must match `GOOGLE_REDIRECT_URI`

## Gmail API Quota

| Operation | Units | Per poll (max 20 msgs) |
|-----------|-------|----------------------|
| messages.list | 5 | 5 |
| messages.get (metadata) | 5 | 100 |
| messages.get (full) | 5 | 100 |
| messages.modify | 5 | 100 |
| **Total per poll** | | **305 units** |

Free tier: 1B units/day. At 1 poll/min: ~440K/day — negligible.
