# Email Integration — Gmail, Outlook, Custom SMTP

Concrete implementation of the three branded email integrations added May 22, 2026.

## Provider Presets (`email_utils.py`)

Three entries in `PROVIDER_PRESETS`:

### email-gmail
- **SMTP**: smtp.gmail.com:587 with STARTTLS
- **IMAP**: imap.gmail.com:993
- **Fields**: email (text), app_password (password)
- **Auth**: Gmail App Password (Google Account → Security → App passwords)
- **Icon**: "G" with Google gradient `linear-gradient(135deg,#4285F4 0%,#34A853 33%,#FBBC05 66%,#EA4335 100%)`

### email-outlook
- **SMTP**: smtp.office365.com:587 with STARTTLS
- **IMAP**: outlook.office365.com:993
- **Fields**: email (text), password (password)
- **Auth**: Password or App Password (if 2FA)
- **Icon**: "O" with `#0072C6`

### email-smtp-custom
- **SMTP**: user-configured host + port (default 587)
- **IMAP**: user-configured host + port (optional)
- **Fields**: smtp_host (text), smtp_port (number), username (text), password (password), from_email (email), imap_host (text, optional), imap_port (number, optional)
- **Icon**: "⚙" with `#6E6E73`

## SMTP Config Resolution

`get_provider_smtp_config(integration_id, user_config)` resolves provider presets:
- For Gmail/Outlook: uses preset's smtp_host/port, user's email as username
- For Custom SMTP: reads all fields directly from user_config

## Connection Test

`test_smtp_connection()` → returns `(success, message)` tuple.
Creates SMTP connection with timeout=10, sends no data.
Returns user-friendly error messages for auth failures, timeouts, etc.

## Catalog Entries (`server.py`)

Each email integration has:
- `configurable: True`
- `email_provider: "email-gmail"` (etc.)
- Category: "messaging"
- No `link` (config is inline)

## Frontend (`dashboard_template.py`)

### CSS Classes
- `.int-config-panel` — outer container, same margin/radius as QR panels
- `.cfg-grid` — 2-column grid for fields
- `.cfg-field.full` — spans both columns (for single-field rows)
- `.cfg-actions` — button row with Connect & Test + Cancel
- `.cfg-status` — result message (`.success` green, `.error` red, `.loading` with spinner)

### JS Functions
- `showEmailConfigPanel(id, card, data)` — builds field HTML from data.fields array, inserts after card
- `saveEmailConfig(id)` — validates required fields, POSTs to save-config, shows green check or red error
- `cancelEmailConfig(id)` — removes panel, resets CONNECTING_IDS
- `openEmailConfig(id)` — re-opens config for connected integrations (from gear icon)
- `removeConfigPanel(id)` — DOM cleanup

### Flow
1. User toggles ON → `POST /api/integrations/{id}/connect` → returns `config_needed` + field schema
2. Config panel renders inline below card
3. Status endpoint called for pre-fill (returns config even if not yet enabled)
4. User fills fields, clicks "Connect & Test"
5. `POST /api/integrations/{id}/save-config` → tests SMTP → if OK, marks enabled, re-renders as "Connected"
6. If connected: gear icon appears for re-opening settings
7. Toggle OFF → `POST /api/integrations/{id}/disconnect` → deletes DB row

## Gmail OAuth (added May 22, 2026)

Gmail now uses Google OAuth 2.0 instead of SMTP App Passwords.

### Google Cloud Setup

1. Create a project at https://console.cloud.google.com
2. Enable Gmail API (APIs & Services > Library)
3. Create OAuth client ID of type "Web application"
4. Set redirect URIs in Google Cloud Console (add both):
   - Production: `https://ara.move78.work/api/integrations/email-gmail/oauth/callback`
   - Local dev: `http://localhost:8766/api/integrations/email-gmail/oauth/callback`
   **The redirect URI in `app/config.py` MUST match one of the entries in GCP.** If they don't match, Google returns `redirect_uri_mismatch` and the OAuth flow silently fails.
5. Copy Client ID and Secret to `/opt/ara/.env` (NOT `~/.hermes/.env` — that's for Hermes itself, not ARA):
   ```
   GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-xxxx
   ```
   The ARA server is a systemd service with `EnvironmentFile=/opt/ara/.env`. Without these env vars, the authorize endpoint returns `{"error": "Google OAuth not configured"}`.
6. Restart the ARA server: `systemctl restart ara-server`

### Dependencies

pip install google-api-python-client google-auth-oauthlib google-auth-httplib2

### Sending via Gmail API

`email_utils.py` has `send_via_gmail_api(tokens, to, subject, body, body_html)`:
- Uses **`gmail.modify`** scope (send + read) — not `gmail.send` (send-only). User explicitly requested read capability for Ava to handle replies to outreach.
- Uses `google.oauth2.credentials.Credentials` with auto-refresh
- Builds Gmail API service with `build("gmail", "v1", credentials=creds)`
- Encodes MIME message as base64url, sends via `service.users().messages().send()`
- Returns `(success, error_message)` tuple — same signature as `send_email()` for interchangeable use

### Token Storage

Stored in `IntegrationConfig.config` JSON column with keys: access_token, refresh_token, token_uri, client_id, client_secret, scopes (list), expiry (ISO timestamp), auth_method ("oauth").

### Endpoints

- `GET /api/integrations/email-gmail/oauth/authorize` — returns `{url: "..."}` consent URL
- `GET /api/integrations/email-gmail/oauth/callback` — receives code, exchanges for tokens, saves to DB, returns HTML page with postMessage + window.close()
- `POST /api/integrations/email-gmail/connect` — returns `{status: "oauth_needed", oauth: true}` (no credential fields)

### Frontend

- `showOAuthPanel(id, card, data)` — renders blue "Sign in with Google" button (no password fields)
- `connectGmailOAuth(id)` — fetches authorize URL, opens centered popup via `window.open()`
- `window.addEventListener('message', ...)` — handles `{type: 'oauth-complete', status: 'connected' | 'error'}` from popup callback

### CSRF Protection

In-memory `_oauth_states` dict: state param -> timestamp. States expire after 10 minutes. Verified on callback before token exchange.

### PKCE Code Verifier (Critical Bug / Fix)

`google-auth-oauthlib >= 1.0` auto-generates PKCE parameters when `Flow.authorization_url()` is called. This produces a `code_challenge` in the redirect URL — but the `code_verifier` is only stored on that **specific Flow instance**. The callback creates a **new** `Flow` with no memory of it.

**Two approaches depending on client type:**

**Approach A — Confidential client (recommended, has client_secret):** Disable PKCE entirely. Google does not require PKCE when a client_secret is provided.

```python
# Authorize endpoint
flow = Flow.from_client_config(..., scopes=..., redirect_uri=...)
flow.autogenerate_code_verifier = False          # <-- key line
auth_url, state = flow.authorization_url(...)
_oauth_states[state] = {"created_at": datetime.now()}

# Callback — simple direct POST, no code_verifier
import requests
resp = requests.post("https://oauth2.googleapis.com/token", data={
    "code": code,
    "client_id": GOOGLE_CLIENT_ID,
    "client_secret": GOOGLE_CLIENT_SECRET,
    "redirect_uri": GOOGLE_REDIRECT_URI,
    "grant_type": "authorization_code",
})
```

The authorize URL will have NO `code_challenge` parameter — confirming PKCE is disabled.

**Approach B — Public client (no client_secret, PKCE required):** Preserve the code_verifier and use direct POST (not `Flow.fetch_token()`):

```python
# Authorize: save code_verifier alongside state
auth_url, state = flow.authorization_url(...)
_oauth_states[state] = {
    "created_at": datetime.now(),
    "code_verifier": getattr(flow, "code_verifier", None),
}

# Callback: direct POST with code_verifier
resp = requests.post("https://oauth2.googleapis.com/token", data={
    "code": code,
    "client_id": GOOGLE_CLIENT_ID,
    "redirect_uri": GOOGLE_REDIRECT_URI,
    "grant_type": "authorization_code",
    "code_verifier": saved_verifier,            # <-- critical
})
```

**Broken pattern (do not use):**
```python
# Creating a new Flow in the callback — PKCE verifier is lost
flow = Flow.from_client_config(...)
__CHECK_MARKER__
flow.fetch_token(code=code)  # Fails with (invalid_grant) Missing code verifier
```

### Token Normalization (Raw → Stored Format)

Google's raw token response differs from the format `send_via_gmail_api()` expects:

| Field | Raw Response | Stored Format |
|-------|-------------|---------------|
| access_token | `"access_token": "ya29..."` | Same |
| refresh_token | `"refresh_token": "1//..."` | Same |
| scope | `"scope": "https://www.googleapis.com/auth/gmail.modify"` (string) | `"scopes": ["https://www.googleapis.com/auth/gmail.modify"]` (list) |
| expires_in | `"expires_in": 3599` (seconds int) | `"expiry": "2026-05-22T14:30:00"` (ISO timestamp) |
| token_uri | Missing | Added: `"https://oauth2.googleapis.com/token"` |
| client_id | Missing | Added: from GOOGLE_CLIENT_ID |
| client_secret | Missing | Added: from GOOGLE_CLIENT_SECRET |
| auth_method | Missing | Added: `"oauth"` |

Normalization code snippet:
```python
import datetime as dt
expiry_dt = dt.datetime.now() + dt.timedelta(seconds=raw.get("expires_in", 3600))
normalized = {
    "access_token": raw["access_token"],
    "refresh_token": raw.get("refresh_token"),
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": GOOGLE_CLIENT_ID,
    "client_secret": GOOGLE_CLIENT_SECRET,
    "scopes": raw.get("scope", GMAIL_SCOPE).split(),
    "expiry": expiry_dt.isoformat(),
    "auth_method": "oauth",
}
```

### Error Messages

| Error | Likely Cause |
|-------|-------------|
| `(invalid_grant) Missing code verifier` | PKCE code_verifier not passed in token exchange. **Fix**: For confidential clients (have client_secret), disable PKCE in the authorize endpoint: `flow.autogenerate_code_verifier = False`. For public clients, see PKCE section above for the direct POST approach. |
| `(invalid_grant) Code was already redeemed.` | Authorization code can only be exchanged once. User probably clicked back/refreshed the popup. Full re-auth required — clear `IntegrationConfig` row and re-authorize. |
| `redirect_uri_mismatch` | Google Cloud Console redirect URI doesn't match what's in code. Must match exactly (including trailing slash). |
| `401 Unauthorized` on send | Access token expired and no refresh_token available (first-time auth with `prompt=consent` should return one). Check `access_type=offline` in the authorize URL. |
| `500 Internal Server Error` on authorize endpoint | `google-auth-oauthlib` not installed. Install: `pip install google-auth-oauthlib`. The authorize endpoint imports `from google_auth_oauthlib.flow import Flow` which raises `ModuleNotFoundError`. |
| `{"error": "Google OAuth not configured..."}`  | `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` not set in `/opt/ara/.env`. The authorize endpoint checks both; returns this error if either is empty. |

### Token Refresh Persistence (Pitfall)

`send_via_gmail_api()` auto-refreshes expired tokens via `creds.refresh(Request())`, but the new `access_token` and `expiry` are **only updated in the in-memory `Credentials` object — never saved back to `IntegrationConfig.config`**. The DB retains the old expired token.

**Consequences:**
- Every send call re-loads expired tokens from DB → re-refreshes → wasted API call
- If the `refresh_token` becomes invalid (revoked, GCP project in testing mode, 6-month inactivity), the DB holds useless tokens indefinitely with no way to detect failure until the next actual send
- The `_live_check_email()` function does its OWN separate token refresh (direct POST to oauth2.googleapis.com/token) but also doesn't persist the result — so the dashboard status check and the actual send path refresh independently, doubling the wasted calls

**Fix:** After `creds.refresh(Request())` in `send_via_gmail_api()`, save the new `access_token` and `expiry` back to the DB. Same for `_live_check_email()`. This requires `db` access in those functions, or the caller must update the config after the call.
