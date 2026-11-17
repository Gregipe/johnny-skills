---
name: ara-email-integration
description: Gmail OAuth + IMAP email integration for ARA — inbound polling, outbound sending, lead matching, stage transitions, and OAuth diagnostic patterns.
category: deployment
trigger: email sending, inbound email replies, Gmail OAuth re-auth, lead engagement via email
---

# ARA Email Integration

Gmail-backed email for ARA — outbound sending via Gmail API (OAuth) + inbound reply polling via Gmail API `listMessages`. When a lead replies to Ava's email, the system detects it, transitions the lead to `engaged`, syncs the deal forward, cancels pending cadence actions, and logs an email conversation thread.

## Architecture

```
Gmail Inbox
    ↓ (polled every 60s by scheduler daemon)
Gmail API: users.messages.list(q="is:unread")
    ↓ (metadata: From header for matching)
Lead lookup: Lead.email ILIKE sender_email
    ↓ (match found)
Gmail API: users.messages.get(format=full)  →  extract body
    ↓
Conversation(logged: channel="email", direction="inbound")
    ↓
Stage transition: reached_out → engaged (matching WhatsApp inbound pattern)
    ↓
Deal sync: _sync_deal_stage_from_lead(lead.id)
    ↓
Cancel pending cadence actions for this lead
    ↓
Gmail API: users.messages.modify(removeLabelIds=["UNREAD"])
```

## Code Locations

| Component | File | Function/Line |
|-----------|------|---------------|
| Token refresh | `email_utils.py` | `refresh_gmail_token()` |
| Inbox poller | `server.py` | `_poll_inbound_gmail()` |
| Body extraction | `server.py` | `_extract_gmail_body()` |
| Scheduler hook | `server.py` | `_run_scheduler()` — after daily summary, before sleep |
| Outbound send | `email_utils.py` | `send_via_gmail_api()` (uses google-api-python-client) |
| OAuth live check | `server.py` | `_live_check_email()` (~line 9038) |
| Deal stage sync | `server.py` | `_sync_deal_stage_from_lead()` (used by both WhatsApp and email) |
| **Email auto-respond** | `server.py` | `_ava_auto_respond_email()` (~line 8524) |
| WhatsApp auto-respond | `server.py` | `_ava_auto_respond()` (~line 8627) |

## Auto-Respond

When a lead replies via email and `lead.assigned_agent == "ava"`, the poller calls `_ava_auto_respond_email()` which:
1. Loads recent conversation history (last 6 messages)
2. Formats `AVA_AUTO_SYSTEM_PROMPT` with lead context + conversation history
3. Calls `call_llm()` to generate a contextual response
4. Sends via `send_via_gmail_api()` using stored OAuth tokens
5. Logs an outbound `Conversation` record with `channel="email"`

This mirrors the WhatsApp auto-respond pattern (`_ava_auto_respond()`) but uses Gmail API instead of `wa.send_message_sync()`.

### Playbook Gap (KNOWN ISSUE)

`AVA_AUTO_SYSTEM_PROMPT` is a **generic** prompt — it does NOT incorporate the cadence's conversational playbook from Outreach Central. The playbook (stored in `CadenceConfig.config.playbook.engaged`) defines:
- **Style:** tone, length, boundaries (e.g. `no_pricing` for engaged cold leads)
- **Escalations:** triggers for human handoff (pricing_negotiation, negative_sentiment, compliance_question)
- **Intent dispositions:** Interested, Considering, Meeting Intent, Not Interested, Busy, Gatekeeper
- **Actions:** summarize, notify owner, send case study

Without playbook injection, Ava may violate the configured rules — e.g. answering pricing questions directly when the playbook says `boundaries: no_pricing` and `escalations.pricing_negotiation: high`.

**Fix needed:** Add `load_playbook_for_prompt(lead, db)` that reads the lead's cadence config playbook for their current stage, and inject it into the auto-respond prompt. This applies to both email AND WhatsApp auto-respond.

## Integration Config

Stored in `integration_config` table, `integration_id = "email-gmail"`:

```json
{
  "access_token": "ya29.a0...",
  "refresh_token": "1//0g...",
  "client_id": "1019340905424-...",
  "client_secret": "GOCSPX-...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "scopes": ["https://www.googleapis.com/auth/gmail.modify"]
}
```

The `config` column also stores `email` (the connected Gmail address) when available — used for self-filtering to avoid processing the owner's own replies as lead replies.

## Inbound Poller Behavior

- **Throttle:** Polls at most once per 60s (module-level `_EMAIL_POLL_LAST` guard)
- **Token refresh:** Checks profile endpoint first; if 401, attempts `refresh_gmail_token()`; if refresh fails, skips polling entirely
- **Self-filter:** Skips messages where `sender_email == connected_email` (prevents owner's own replies from matching as lead replies)
- **Unknown senders:** Marked as read immediately (no re-processing each cycle)
- **Max 20 messages per poll:** `maxResults=20` on the list call
- **Error resilience:** All Gmail API calls wrapped in try/except; failures logged, not fatal

## Stage Transition Pattern

The inbound email handler follows the exact same pattern as the WhatsApp inbound handler (server.py `_handle_inbound_whatsapp` at line ~8174):

```python
# 1. Log conversation
conv = Conversation(lead_id=lead.id, tenant_id=TENANT_ID, channel="email",
                    direction="inbound", subject=f"Re: {subject}", content=body, ...)
db.add(conv)

# 2. Update lead timestamps
now_dt = utcnow()
lead.last_contacted_at = now_dt
if not lead.first_reply_at:
    lead.first_reply_at = now_dt

# 3. Stage transition
if lead.stage in ("new", "reached_out"):
    lead.stage = "engaged"
    lead.updated_at = utcnow()
    lead.lead_source = "email"
    db.commit()
    _sync_deal_stage_from_lead(lead.id)

# 4. Cancel pending cadence actions
pending = db.query(ScheduledAction).filter(
    ScheduledAction.tenant_id == TENANT_ID,
    ScheduledAction.lead_id == lead.id,
    ScheduledAction.status.in_(["pending", "firing"]),
).all()
for pa in pending:
    pa.status = "cancelled"
    pa.executed_at = utcnow()
```

## Gmail API Quota

Free tier: 1B quota units/day.
- `messages.list` (metadata): ~5 units
- `messages.get` (full): ~5 units
- `messages.modify`: ~5 units
- At 1 poll/min with 20 messages max: negligible usage. Safe.

## Deployment Paths

### Production (Hetzner VPS)
`/opt/ara` exists — server runs normally. Inbound email polling starts automatically with the scheduler daemon.

### macOS (Development)
`/opt/ara` is root-owned and may not exist. The server hardcodes `/opt/ara` for database, .env, and uploads — if the directory doesn't exist, startup crashes. Full setup:

```bash
# 1. Create /opt/ara (requires sudo on macOS)
sudo mkdir -p /opt/ara/uploads && sudo chown $(whoami) /opt/ara /opt/ara/uploads

# 2. Copy the database
cp /Users/greg/ara/ara.db /opt/ara/ara.db

# 3. Copy/create .env with OAuth credentials
# Must contain: GOOGLE_CLIENT_ID=... and GOOGLE_CLIENT_SECRET=...
cp /Users/greg/ara/.env /opt/ara/.env   # or create manually

# 4. Clear Python bytecode cache (avoids stale prompt/tool schema issues)
find /Users/greg/ara -path "*/__pycache__/*.pyc" -delete

# 5. Start server
cd /Users/greg/ara && ./venv/bin/python -u server.py
```

Without step 1, the server crashes at startup with `PermissionError: [Errno 13] Permission denied: '/opt/ara'`.
Without step 2, the server creates an empty database — no leads, tenants, or integrations exist.
Without step 3, the OAuth callback endpoint returns `"Google OAuth not configured"` because `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` env vars are empty.

## Common Pitfalls

### 0. LLM API Key Masked Failure (CRITICAL)
**Symptom:** Auto-responses silently never fire. No `[email]` log lines about LLM calls. Outbound conversations never appear. Server shows no errors.

**Root cause:** `call_llm()` in `induction_engine.py` catches ALL exceptions and returns `"⚠️ I encountered an issue processing your request."`. If `DEEPSEEK_API_KEY` is invalid/expired, this ⚠️ message is returned, `_ava_auto_respond_email()` checks `response.startswith("⚠️")` and skips sending. The failure is completely silent.

**Diagnosis:**
```bash
cd /opt/ara && venv/bin/python -c "
import os, requests
with open('/root/.hermes/.env') as f:
    for line in f:
        if line.startswith('DEEPSEEK_API_KEY='):
            os.environ['DEEPSEEK_API_KEY'] = line.split('=',1)[1].strip()
resp = requests.post('https://api.deepseek.com/v1/chat/completions',
    headers={'Authorization': f'Bearer {os.environ[\"DEEPSEEK_API_KEY\"]}', 'Content-Type': 'application/json'},
    json={'model': 'deepseek-chat', 'messages': [{'role':'user','content':'hi'}], 'max_tokens': 10})
print(f'Status: {resp.status_code} — {resp.text[:200]}')
"
```
401 with `"Authentication Fails"` means the key is invalid. Update it in `/root/.hermes/.env`.

**Fix:** Replace `DEEPSEEK_API_KEY` in `/root/.hermes/.env` with the active key from DeepSeek dashboard. The systemd service loads this file via `load_dotenv("/root/.hermes/.env")` in server.py line 62.

### 1. Gmail OAuth "deleted_client" (CRITICAL)
**Symptom:** Token refresh returns HTTP 401 with `{"error": "deleted_client", "error_description": "The OAuth client was deleted."}`. All Gmail API calls fail. The integration shows `connected: false` on the dashboard.

**Root cause:** The Google Cloud project's OAuth client ID was deleted or revoked. The `client_id` and `client_secret` stored in `integration_config.config` no longer exist.

**Diagnosis:**
```bash
cd /Users/greg/ara && venv/bin/python -c "
import json, urllib.request, urllib.parse, sqlite3
db = sqlite3.connect('ara.db')
row = db.execute(\"SELECT config FROM integration_config WHERE integration_id='email-gmail'\").fetchone()
config = json.loads(row[0])
data = urllib.parse.urlencode({
    'client_id': config['client_id'],
    'client_secret': config['client_secret'],
    'refresh_token': config['refresh_token'],
    'grant_type': 'refresh_token',
}).encode()
req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data,
    headers={'Content-Type': 'application/x-www-form-urlencoded'})
try:
    resp = urllib.request.urlopen(req, timeout=15)
    print('Token refreshed OK')
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}: {e.read().decode()[:200]}')
"
```

**Fix — full re-authentication procedure:**

1. **Get new OAuth client credentials** from Google Cloud Console → APIs & Services → Credentials
2. **Update the integration_config DB row** with new `client_id` and `client_secret`, clear old tokens:
   ```bash
   sqlite3 /opt/ara/ara.db "
   UPDATE integration_config
   SET config = json_set(json_set(json_set(json_set(config,
       '$.client_id', 'NEW_CLIENT_ID.apps.googleusercontent.com'),
       '$.client_secret', 'NEW_SECRET'),
       '$.access_token', ''),
       '$.refresh_token', '')
   WHERE integration_id = 'email-gmail';
   "
   ```
3. **Update `/opt/ara/.env`** with `GOOGLE_CLIENT_ID=...` and `GOOGLE_CLIENT_SECRET=...` (the OAuth callback endpoint reads these as fallbacks)
4. **Restart the server**
5. **Run the OAuth flow:** open `http://localhost:8766/api/integrations/email-gmail/oauth/authorize` in a browser → Google consent → callback stores fresh tokens
6. **Verify:** `curl http://localhost:8766/api/integrations/email-gmail/status` should return `connected: true`

**Note:** `GOOGLE_REDIRECT_URI` is now configurable via env var. Defaults to `https://ara.move78.work/api/integrations/email-gmail/oauth/callback` but can be overridden for local testing:
```bash
echo 'GOOGLE_REDIRECT_URI=http://localhost:8766/api/integrations/email-gmail/oauth/callback' >> /opt/ara/.env
```
The Google Cloud Console OAuth client must have the matching redirect URI registered.

### 2. Access Token Also Expired
**Symptom:** Even the profile check (`GET /gmail/v1/users/me/profile`) returns 401. Both `access_token` and `refresh_token` are dead.

**Diagnosis:** Test the access token directly:
```bash
curl -H "Authorization: Bearer $(cd /Users/greg/ara && venv/bin/python -c "import json,sqlite3;db=sqlite3.connect('ara.db');c=json.loads(db.execute(\"SELECT config FROM integration_config WHERE integration_id='email-gmail'\").fetchone()[0]);print(c.get('access_token',''))")" \
  https://gmail.googleapis.com/gmail/v1/users/me/profile
```

**Fix:** Same as pitfall #1 — full OAuth re-authentication needed.

### 3. `/opt/ara` Doesn't Exist on macOS
**Symptom:** Server crashes at startup with `PermissionError: [Errno 13] Permission denied: '/opt/ara'`.

**Root cause:** `server.py` hardcodes `UPLOAD_DIR = "/opt/ara/uploads"` and calls `os.makedirs(UPLOAD_DIR, exist_ok=True)`. On macOS, `/opt` is root-owned and `exist_ok=True` doesn't help when the parent directory can't be traversed.

**Fix:** `sudo mkdir -p /opt/ara/uploads && sudo chown greg /opt/ara /opt/ara/uploads`

### 4. Scheduler Not Running the Poller
**Symptom:** No `[email]` log lines appear in server output. Leads stay at `reached_out` despite replying to emails.

**Diagnosis:** Check if the server was restarted with the new code:
```bash
grep "Inbound email poll" /tmp/ara-server.log
```
If no matches, the server is running old code. Kill and restart.

### 5. Self-Reply Matching
**Symptom:** The owner's own email replies get matched as lead replies, creating bogus engaged leads.

**Fix:** The poller compares `sender_email` against `config.get("email")` (the connected Gmail address). If they match, the message is skipped. Ensure the `email` field is present in the integration config.

### 7. Attachments Missing from Outbound Emails
**Symptom:** `send_email` tool accepts `attachment` parameter, email is sent, but no file attached. Scheduler logs "Attachment file not found: /opt/ara/uploads/..."

**Root cause — four possible failures:**
1. **Empty uploads directory:** Files exist in DB (`documents` table) but actual PDFs are missing from `/opt/ara/uploads/`. Dashboard uploads save files to disk; legacy documents from migrations may not have binaries.
2. **PDF text_content fallback (FIXED June 25, 2026):** When the original binary is missing and `doc.text_content` is non-empty, the scheduler fell back to creating a temp `.txt` file with extracted text. For PDFs/decks, this sent a useless text extract (10KB) instead of the actual deck (5MB). Now BLOCKED for `.pdf` files — if the original binary is missing, the attachment is skipped with a warning rather than sending extracted text.
3. **Dispatch path doesn't read attachments:** `_execute_action` for email type was calling `send_via_gmail_api(tokens, email, subject, body)` without passing `attachments` parameter. Fixed June 2026.
4. **Filename mismatch:** LLM hallucinated filename doesn't match the file on disk. The dispatch code does exact filename match against the Documents table, then constructs path as `UPLOAD_DIR/{doc.id}_{doc.filename}`.

**Diagnosis:**
```bash
# Check if uploads directory has files
ls -la /opt/ara/uploads/

# Check what documents exist in DB
sqlite3 /opt/ara/ara.db "SELECT id, filename FROM documents;"
```

**Fix:** Re-upload files via dashboard (not chat). See `references/email-attachment-support-june2026.md` in `ara-agent-tools` for full dispatch pattern.
**Symptom:** Token refreshes on every poll cycle, causing rate-limiting.

**Root cause:** The refreshed token is written to `cfg.config["access_token"]` and `db.commit()` is called, but the `config` dict is a local reference. If the DB session is closed and reopened, the old token is read again.

**Fix:** The poller uses the scheduler's active DB session. Token refresh happens inline and commits to the same session. As long as the scheduler loop reuses one session per cycle, the refreshed token persists for that cycle. If this becomes unreliable, add a module-level `_EMAIL_ACCESS_TOKEN` cache with a TTL.

## References
- `references/gmail-oauth-diagnostics.md` — Full OAuth token refresh diagnostic script
- `references/end-to-end-test-checklist.md` — Full test checklist
- `references/ara-email-pipeline-notes.md` — Historical inbound pipeline notes (archived from ara-email-pipeline)
