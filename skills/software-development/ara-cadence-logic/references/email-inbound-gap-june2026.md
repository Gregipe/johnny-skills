# Email Inbound Gap — June 2026

ARA's email integration is **outbound-only**. Lead replies to outreach emails are invisible to the system.

## What Exists

- `email_utils.py` — SMTP sending, provider presets (Gmail, Outlook, Custom SMTP)
- `server.py` — Gmail OAuth flow for sending via Gmail API (`send_via_gmail_api`)
- `server.py` — `_live_check_email()` verifies SMTP/OAuth connectivity (outbound only)
- `email_utils.py` — `imaplib` is imported but never used anywhere in the codebase

## What's Missing

- No IMAP polling loop
- No Gmail push notifications / pub/sub webhook
- No scheduler task that checks inboxes for replies
- No `In-Reply-To` header matching to outbound messages
- No stage transition trigger on email reply (reached_out → engaged)
- No conversation thread creation for email replies
- No Ava auto-response to email replies

## Diagnosis Pattern

When Greg says "I replied to Ava's email as a lead and nothing happened":

```bash
# 1. Confirm it IS an email issue (not WhatsApp)
# 2. Check the lead exists with the email address used
sqlite3 /Users/greg/ara/ara.db "SELECT id, name, stage, email FROM leads WHERE email LIKE '%gregipe%'"
# 3. Lead will be at 'reached_out' — no stage transition occurred
# 4. No conversation entry will exist for the reply
```

## What Would Need to Be Built

1. **IMAP polling loop** — Background thread/scheduler that checks the connected inbox every 30-60s
2. **Reply matching** — Match inbound emails to leads by:
   - `In-Reply-To` / `References` header → matching to the outbound message ID
   - Fallback: `From` email address → matching to lead.email
3. **Stage transition** — On matched reply: lead.stage = "engaged", record source_channel = "email"
4. **Conversation recording** — Create a Conversation entry with direction="inbound" and the reply text
5. **Auto-response** — Optionally trigger `_ava_auto_respond()` similar to the WhatsApp path
6. **Dedup** — Track seen message IDs to prevent double-processing

## Current Workaround

Lead email replies land in Greg's Gmail inbox. To advance the pipeline manually:
- Open the lead in the dashboard
- Manually change stage to "engaged"
- Paste the email content into the lead's chat/notes

## Related

- `ara-agent-chat-debugging` — Layer 0 (confirm the channel first) + Layer 1-E (email channel diagnostics)
- `whatsapp-integration` — WhatsApp inbound pipeline for comparison (what a working inbound pipeline looks like)
