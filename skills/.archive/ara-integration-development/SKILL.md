---
name: ara-integration-development
description: "Add a new configurable integration to the ARA dashboard — backend DB model, provider presets, API endpoints, and inline config panel UI. Covers the full-stack pattern for any channel (email, SMS, calendar, voice). WhatsApp integration now uses Baileys sidecar (see whatsapp-web-automation skill)."
---

# ARA Integration Development

Full-stack pattern for wiring up a configurable integration in ARA (Autonomous Revenue Agent).

## Trigger

- User says "add [Gmail/Twilio/Telegram/etc.] integration to the dashboard"
- User says "give the option for the customer to setup [channel] on the integrations page"
- You need to add a new item to the INTEGRATIONS_CATALOG that requires user-provided credentials (API keys, SMTP settings, tokens)

## Sequence

### 0. Clarify First

Ask the user:
- **How many provider options?** (e.g., Gmail + Outlook + SMTP vs just one)
- **Inline vs modal for setup?** ARA uses inline panels (expands below the card, same pattern as WhatsApp QR)
- **Branded icons?** Each option should have a distinct icon/logo and brand color

### 1. Database

`database.py` should already have `IntegrationConfig`. If it doesn't, add it:

```
class IntegrationConfig(Base):
    __tablename__ = "integration_config"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    integration_id = Column(String, nullable=False)  # e.g. "email-gmail"
    config = Column(JSON, default=dict)              # provider-specific settings
    enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
```

If `IntegrationConfig` already exists, you just need a new `integration_id` value — no DB changes needed.

### 2. Utility Module (optional)

For complex integrations, create a module (e.g. `email_utils.py`, `sms_utils.py`) with:

```python
PROVIDER_PRESETS = {
    "email-gmail": {
        "label": "Gmail",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_tls": True,
        "fields": [
            {"key": "email", "label": "Email Address", "type": "email", "placeholder": "you@gmail.com"},
            {"key": "app_password", "label": "App Password", "type": "password", "placeholder": "16-char password"},
        ],
        "test_requires": ["email", "app_password"],
    },
}
```

Include: provider presets (connection defaults + field schemas), a connection test function, and the primary action function (send email, send SMS, etc.).

### 3. Backend API (`server.py`)

**a) Import** the new module.

**b) Add entries to `INTEGRATIONS_CATALOG`**:

```python
{
    "id": "my-integration",
    "name": "Display Name",
    "subtitle": "Short label",
    "description": "What it does. Keep concise.",
    "icon": "G",                        # letter or emoji
    "icon_bg": "#HEXCODE",              # solid color or gradient
    "category": "messaging",            # messaging | phone | productivity
    "coming_soon": False,
    "configurable": True,               # MUST be True for config-panel flow
    "email_provider": "my-integration", # optional internal routing key
}
```

**c) Update `_get_integration_status()`**:

**Prefer live connection testing over pure DB state.** A DB row with `enabled=True` does not mean the integration actually works — credentials can expire (OAuth tokens), servers can go down, API keys can be revoked. Live-test each integration type.

```python
if integration_id == "email-gmail":
    cfg = db.query(IntegrationConfig).filter_by(
        tenant_id=tenant.id, integration_id=integration_id,
    ).first()
    if cfg and cfg.enabled and cfg.config:
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            creds = Credentials(**cfg.config)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            return {"connected": True, "authenticated": True, "config": cfg.config}
        except Exception:
            return {"connected": False, "authenticated": False, "config": cfg.config}
    return {"connected": False, "authenticated": False, "config": cfg.config if cfg else {}}

elif integration_id == "email-smtp-custom":
    cfg = db.query(IntegrationConfig).filter_by(
        tenant_id=tenant.id, integration_id=integration_id,
    ).first()
    if cfg and cfg.enabled and cfg.config:
        try:
            import smtplib
            smtp = smtplib.SMTP(cfg.config.get("smtp_host", ""), int(cfg.config.get("smtp_port", 587)), timeout=10)
            smtp.starttls()
            smtp.login(cfg.config.get("username", ""), cfg.config.get("password", ""))
            smtp.quit()
            return {"connected": True, "authenticated": True, "config": cfg.config}
        except Exception:
            return {"connected": False, "authenticated": False, "config": cfg.config}
    return {"connected": False, "authenticated": False, "config": cfg.config if cfg else {}}

else:  # Fallback — DB-only check
    cfg = db.query(IntegrationConfig).filter_by(
        tenant_id=tenant.id, integration_id=integration_id,
    ).first()
    enabled = cfg is not None and cfg.enabled and bool(cfg.config)
    return {"connected": enabled, "authenticated": enabled, "config": cfg.config if cfg else {}}
```

**Why live checking matters:** The dashboard shows a connected/unconnected toggle. DB-only checks can show "Connected ✓" for expired OAuth tokens or dead SMTP servers, misleading users into thinking everything works when it doesn't. Live-testing on every status poll means the dashboard reflects reality.

**d) Update `connect_integration()`**:

```python
if integration_id in ("my-integration",):
    preset = PROVIDER_PRESETS.get(integration_id)
    return {"status": "config_needed", "provider": integration_id, "label": preset["label"], "fields": preset["fields"]}
```

**e) Update `disconnect_integration()`** — delete the IntegrationConfig row.

**f) Add `save-config` endpoint**:

```python
@app.post("/api/integrations/{integration_id}/save-config")
def save_integration_config(integration_id: str, data: dict):
    # Save to DB, test connection, mark enabled on success
    success, message = test_connection(integration_id, data)
    if success:
        cfg.enabled = True; db.commit()
        return {"status": "connected", "message": "Connected"}
    return {"status": "error", "message": f"Failed: {message}"}
```

**g) Add `status` endpoint** (for UI pre-fill):

```python
@app.get("/api/integrations/{integration_id}/status")
def get_integration_status(integration_id: str):
    return _get_integration_status(integration_id)
```

### 4. Frontend (`dashboard_template.py`)

**a) Add CSS** for the config panel. Reference the existing `.int-config-panel` classes.

**d) Update `toggleIntegration()`** to handle `config_needed`:

```javascript
} else if (data.status === 'config_needed') {
    showEmailConfigPanel(id, card, data);
}
```

**⚠️ Critical: Set `CONNECTING_IDS[id] = true` BEFORE the fetch call.** The 5-second auto-poll timer fires `renderIntCards()` which wipes all dynamically-inserted panels. If the config panel is inserted AFTER the fetch but the auto-poll fires BETWEEN the toggle click and the fetch response, the panel never appears.

**Note: `toggleIntegration()` is an `async` function** — it uses `await` on the fetch call. The CONNECTING_IDS guard must be set synchronously BEFORE the first `await` because the 5-second auto-poll can fire between microtasks. Verify the function signature is `async function toggleIntegration(el) { ... }`, not a plain function.

```javascript
// CORRECT — protect against auto-poll race (async function)
async function toggleIntegration(el) {
    var id = el.getAttribute('data-id');
    var card = el.closest('.int-card') || document.querySelector('[data-id="' + id + '"]');
    
    if (!el.checked) {
        CONNECTING_IDS[id] = true;
        await fetch('/api/integrations/' + id + '/disconnect', { method: 'POST' });
        delete CONNECTING_IDS[id];
        removeConfigPanel(id);
        renderIntCards();
        return;
    }
    
    CONNECTING_IDS[id] = true;
    var r = await fetch('/api/integrations/' + id + '/connect', { method: 'POST' });
    var data = await r.json();
    if (data.status === 'config_needed') {
        showEmailConfigPanel(id, card, data);
    } else if (data.oauth) {
        showOAuthPanel(id, card, data);
    } else if (data.status === 'connected') {
        delete CONNECTING_IDS[id];
        setTimeout(renderIntCards, 500);
    } else {
        delete CONNECTING_IDS[id];
        el.checked = false;
    }
}
```

**c) Add JS functions** (adapt names as needed):
- `showEmailConfigPanel(id, card, data)` — renders fields below the card via `card.insertAdjacentHTML('afterend', ...)`
- `saveEmailConfig(id)` — collects field values, POSTs to save-config, validates required fields
- `cancelEmailConfig(id)` — removes panel, resets state
- `removeConfigPanel(id)` — DOM removal
- `openEmailConfig(id)` — re-opens config for already-connected integrations (from gear icon)

**d) Update card rendering** to show a gear icon for connected+configurable:

```javascript
(connected && ix.configurable
  ? '<button class="int-qr-refresh" onclick="event.stopPropagation();openEmailConfig(\\'' + ix.id + '\\')" title="Edit settings">⚙</button>'
  : '')
```

**e) Update event delegation** — card clicks should trigger toggle, but gear icon clicks need `event.stopPropagation()`.

### 5. OAuth Integration Pattern

For providers that support OAuth (Gmail, Slack, Google Calendar, etc.) instead of API key / password auth.

#### Flow Overview

```
Toggle ON → connect returns {oauth: true} → showOAuthPanel() → click "Sign in with Google"
  → fetch /oauth/authorize → {url: "https://accounts.google.com/..."}
  → window.open(url, ...) → popup to Google consent → user approves
  → Google redirects to /oauth/callback?code=...&state=...
  → backend exchanges code for tokens, saves to DB
  → callback renders HTML with postMessage → closes popup
  → listener in dashboard updates UI: "Connected ✓"
```

#### Backend Endpoints

**Authorize endpoint** (`GET /api/integrations/{id}/oauth/authorize`):

```python
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = "http://localhost:8766/api/integrations/email-gmail/oauth/callback"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
_oauth_states: dict = {}  # state -> {"created_at": datetime}

@app.get("/api/integrations/email-gmail/oauth/authorize")
def gmail_oauth_authorize():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return {"error": "Google OAuth not configured"}

    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(
        {"web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }},
        scopes=GMAIL_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
    )

    # Confidential client — disable PKCE (auto-enabled in google-auth-oauthlib >= 1.0)
    flow.autogenerate_code_verifier = False

    auth_url, state = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true",
    )

    # Store state for CSRF verification
    _oauth_states[state] = {"created_at": datetime.now()}

    # Clean stale states (older than 10 min)
    now = datetime.now()
    stale = [s for s, v in _oauth_states.items() if (now - v["created_at"]).total_seconds() > 600]
    for s in stale:
        _oauth_states.pop(s, None)

    return {"url": auth_url}
```

**Callback endpoint** (`GET /api/integrations/{id}/oauth/callback`):

```python
from fastapi.responses import HTMLResponse
import requests as http_requests

@app.get("/api/integrations/email-gmail/oauth/callback")
def gmail_oauth_callback(code: str = None, state: str = None, error: str = None):
    if error:
        return HTMLResponse(f"""<script>
        window.opener.postMessage({{type:'oauth-complete',integration:'email-gmail',status:'error',error:'{error}'}}, '*');
        window.close();</script>""")

    if state not in _oauth_states:
        return HTMLResponse("<p>Invalid state</p>", status_code=400)

    _oauth_states.pop(state, None)

    # Exchange the authorization code for tokens via direct POST
    # (PKCE is disabled for this confidential client — see authorize endpoint)
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    resp = http_requests.post("https://oauth2.googleapis.com/token", data=token_data)
    if not resp.ok:
        return HTMLResponse(f"""<script>
        window.opener.postMessage({{type:'oauth-complete',integration:'email-gmail',status:'error',error:'Token exchange: {resp.status_code}'}}, '*');
        window.close();</script>""")

    raw_tokens = resp.json()

    # Normalize raw Google response into the format send_via_gmail_api() expects
    from datetime import datetime, timedelta
    expiry_dt = datetime.now() + timedelta(seconds=raw_tokens.get("expires_in", 3600))
    tokens = {
        "access_token": raw_tokens["access_token"],
        "refresh_token": raw_tokens.get("refresh_token"),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "scopes": raw_tokens.get("scope", "https://www.googleapis.com/auth/gmail.modify").split(),
        "expiry": expiry_dt.isoformat(),
        "auth_method": "oauth",
    }

    # Save to IntegrationConfig
    cfg = db.query(IntegrationConfig).filter_by(tenant_id=tenant.id, integration_id="email-gmail").first()
    if cfg:
        cfg.config = tokens; cfg.enabled = True
    else:
        db.add(IntegrationConfig(tenant_id=tenant.id, integration_id="email-gmail", config=tokens, enabled=True))
    db.commit()

    return HTMLResponse("""<script>
    window.opener.postMessage({type:'oauth-complete',integration:'email-gmail',status:'connected'}, '*');
    window.close();</script>
    <p>Connected! Close this window.</p>""")
```

**Key**: The callback must return `HTMLResponse` (not JSON) because Google redirects a browser to it. The HTML uses `postMessage` + `window.close()` to communicate back to the SPA popup opener.

**Update the connect endpoint** for OAuth providers — check for existing tokens first, return `oauth: true` instead of fields:

```python
if integration_id in ("email-gmail", "email-outlook", "email-smtp-custom"):
    status = _get_integration_status(integration_id)
    if status.get("authenticated") or status.get("connected"):
        return {"status": "connected", "message": "Already connected"}

    if integration_id == "email-gmail":  # OAuth-based
        return {"status": "oauth_needed", "provider": integration_id, "oauth": True}

    # SMTP-based (Outlook, Custom)
    preset = PROVIDER_PRESETS.get(integration_id)
    return {"status": "config_needed", "provider": integration_id, "fields": preset["fields"]}
```

#### Frontend

**showOAuthPanel()** — renders a "Sign in with Google" button (no credential fields):

```javascript
function showOAuthPanel(id, card, data) {
  removeConfigPanel(id);
  var panelHtml =
    '<div id="cfg-' + id + '" class="int-config-panel">' +
      '<div class="cfg-title">Connect Gmail</div>' +
      '<div class="cfg-grid"><div style="padding:16px;text-align:center">' +
        '<button class="cfg-btn google-btn" id="cfg-' + id + '-oauth-btn" onclick="connectGmailOAuth(\\'' + id + '\\')">' +
          '<span class="google-icon">G</span> Sign in with Google' +
        '</button>' +
      '</div></div>' +
      '<div class="cfg-actions">' +
        '<button class="cfg-btn secondary" onclick="cancelEmailConfig(\\'' + id + '\\')">Cancel</button>' +
        '<div id="cfg-' + id + '-status" class="cfg-status"></div>' +
      '</div>' +
    '</div>';
  card.insertAdjacentHTML('afterend', panelHtml);
}
```

**connectGmailOAuth()** — fetches the auth URL and opens a popup:

```javascript
async function connectGmailOAuth(id) {
  var statusEl = document.getElementById('cfg-' + id + '-status');
  statusEl.innerHTML = '<span class="cfg-spinner"></span> Opening Google sign-in...';
  try {
    var r = await fetch('/api/integrations/email-gmail/oauth/authorize');
    var data = await r.json();
    if (data.error) { statusEl.textContent = '✗ ' + data.error; return; }
    var popup = window.open(data.url, 'google-oauth',
      'width=500,height=700,left=' + (screen.width / 2 - 250) + ',top=100');
    if (!popup || popup.closed) {
      statusEl.textContent = '✗ Popup blocked — allow popups for this site';
    }
  } catch(e) {
    statusEl.textContent = '✗ Error: ' + e.message;
  }
}
```

**postMessage listener** — handles the callback from the popup:

```javascript
window.addEventListener('message', function(event) {
  if (event.data && event.data.type === 'oauth-complete') {
    var id = event.data.integration || 'email-gmail';
    var panel = document.getElementById('cfg-' + id);
    if (event.data.status === 'connected') {
      if (panel) {
        panel.innerHTML = '<div class="cfg-title" style="color:#2e7d32">✓ Connected!</div>' +
          '<div class="cfg-grid" style="text-align:center;padding:16px;color:#555">' +
            '<p>Connected successfully.</p></div>';
      }
      setTimeout(renderIntCards, 800);
    } else if (event.data.status === 'error') {
      var statusEl = document.getElementById('cfg-' + id + '-status');
      if (statusEl) statusEl.textContent = '✗ ' + (event.data.error || 'Auth failed');
    }
  }
});
```

#### CSS for Google Button

```css
.int-config-panel .cfg-btn.google-btn {
  display: inline-flex; align-items: center; gap: 10px;
  background: #fff; color: #1a73e8; border: 2px solid #dadce0;
  padding: 10px 28px; border-radius: 8px; font-size: 14px;
  font-weight: 600; cursor: pointer; transition: all 0.15s;
}
.int-config-panel .cfg-btn.google-btn:hover { background: #f8faff; border-color: #1a73e8; }
.int-config-panel .google-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 24px; height: 24px; background: #1a73e8; color: #fff;
  border-radius: 50%; font-size: 13px; font-weight: 700;
}
```

#### PKCE Handling in google-auth-oauthlib

`google-auth-oauthlib >= 1.0` auto-generates PKCE parameters when `Flow.authorization_url()` is called. This produces a `code_challenge` in the redirect URL — but the `code_verifier` is only stored on that **specific Flow instance**. If you create a **new** `Flow` in the callback, the verifier is lost and Google rejects the token exchange with `(invalid_grant) Missing code verifier`.

**Two approaches depending on client type:**

**Approach A — Confidential client (has client_secret, recommended):** Disable PKCE entirely. Google does not require PKCE for clients with a client_secret. This is simpler and eliminates the verifier management problem.

```python
flow = Flow.from_client_config(
    {"web": {"client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET, ...}},
    scopes=GMAIL_SCOPES,
    redirect_uri=GOOGLE_REDIRECT_URI,
)
# Disable PKCE — google-auth-oauthlib >= 1.0 auto-enables it
flow.autogenerate_code_verifier = False

auth_url, state = flow.authorization_url(access_type="offline", prompt="consent", ...)
_oauth_states[state] = {"created_at": datetime.now()}
```

Callback is then a simple direct POST without code_verifier:

```python
import requests
resp = requests.post("https://oauth2.googleapis.com/token", data={
    "code": code,
    "client_id": GOOGLE_CLIENT_ID,
    "client_secret": GOOGLE_CLIENT_SECRET,
    "redirect_uri": GOOGLE_REDIRECT_URI,
    "grant_type": "authorization_code",
})
```

**Approach B — Public client (no client_secret):** PKCE is required. Preserve the `code_verifier` across the authorize-callback boundary, then bypass `Flow.fetch_token()` with a direct POST:

```python
# Authorize: save code_verifier alongside state
auth_url, state = flow.authorization_url(...)
_oauth_states[state] = {
    "created_at": datetime.now(),
    "code_verifier": flow.code_verifier,  # capture before it's lost
}

# Callback: direct POST with code_verifier (DO NOT use Flow.fetch_token)
resp = requests.post("https://oauth2.googleapis.com/token", data={
    "code": code,
    "client_id": GOOGLE_CLIENT_ID,
    "redirect_uri": GOOGLE_REDIRECT_URI,
    "grant_type": "authorization_code",
    "code_verifier": saved_verifier,
})
```

#### Token Normalization

Google's raw token response differs from the format `send_via_gmail_api()` expects. Normalize the response before saving:

```python
import datetime as dt
expiry_dt = dt.datetime.now() + dt.timedelta(seconds=raw.get("expires_in", 3600))
tokens = {
    "access_token": raw["access_token"],
    "refresh_token": raw.get("refresh_token"),
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": GOOGLE_CLIENT_ID,
    "client_secret": GOOGLE_CLIENT_SECRET,
    "scopes": raw.get("scope", "https://www.googleapis.com/auth/gmail.modify").split(),
    "expiry": expiry_dt.isoformat(),
    "auth_method": "oauth",
}
```

#### OAuth UX Choice: Popup vs Redirect

When building the OAuth flow, **always offer the user both options** and let them choose:

| Option | Flow | Trade-offs |
|--------|------|------------|
| **A. Redirect** | Click → full page navigates to Google → consent → redirected back to dashboard | Simpler to implement, no popup blockers, works on mobile. Page reloads. |
| **B. Popup** | Click → small popup opens → consent → popup closes via postMessage → dashboard stays unchanged | Slicker UX (no page reload), but popup blockers may block it. Requires postMessage listener + callback HTML page. More code to maintain. |

**Implementation notes for Popup (Option B):**
- Callback endpoint must return `HTMLResponse` (not JSON) so the popup can render the `postMessage` + `window.close()` script
- The opener window must have a `window.addEventListener('message', ...)` handler before the popup is opened
- Handle popup blocked case: `if (!popup || popup.closed) { statusEl.textContent = '✗ Popup blocked'; }`
- Popup dimensions: `width=500,height=700,left=' + (screen.width/2 - 250) + ',top=100` — centered on screen

#### Dependencies

```bash
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

#### Token Storage

Store OAuth tokens in `IntegrationConfig.config` (JSON column). The `_get_integration_status()` already returns `connected: true` when `config` is non-empty and `enabled=True`, so no status-handler changes are needed for OAuth tokens — they work with the same pattern as SMTP credentials.

For sending, use the stored tokens with `google.oauth2.credentials.Credentials` and auto-refresh when expired:

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

creds = Credentials(
    token=tokens.get("access_token") or tokens.get("token"),
    refresh_token=tokens.get("refresh_token"),
    token_uri=tokens.get("token_uri", "https://oauth2.googleapis.com/token"),
    client_id=tokens.get("client_id", ""),
    client_secret=tokens.get("client_secret", ""),
    scopes=tokens.get("scopes", ["https://www.googleapis.com/auth/gmail.modify"]),
)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())

service = build("gmail", "v1", credentials=creds)
# send via Gmail API
```

## Pitfalls

- **showOAuthPanel MUST include a cfg-{id}-status div**: The `connectGmailOAuth()` function updates status messages via `document.getElementById('cfg-' + id + '-status')`. If this div is missing from `showOAuthPanel()` HTML, clicking "Sign in with Google" silently does nothing — no error shown, no progress indicator, just a dead button. The status div is the only feedback channel for the entire OAuth flow. Always include it:
  ```javascript
  '<div id="cfg-' + id + '-status" class="cfg-status"></div>' +
  ```
- **Prefer event delegation over inline onclick**: When building config panel buttons in JS, use `data-*` attributes and delegated listeners rather than inline `onclick=\\"..."` with string arguments. This avoids the Python-triple-quoted-string escaping problem entirely. For simple cases where inline is unavoidable, see the "JS in Python strings" section below.
- **Pre-fill failed configs**: When an integration fails to connect, keep the filled-in values in the config panel so the user can correct and retry without re-entering everything.
- **Test-before-enable**: Always test the connection before setting `enabled=True`. Return a clear, user-friendly error message (not a traceback).
- **Gradient icon_bg**: When using `linear-gradient()` for `icon_bg`, ensure proper quoting in the HTML template string.
- **Inline placement**: Use `card.insertAdjacentHTML('afterend', ...)` to place config panels after the card (same pattern as WhatsApp QR).
- **Closing other panels**: When opening a new config panel, close any others that are open to avoid visual clutter.
- **Toggle off = full cleanup**: Disconnect must delete the DB row so the status endpoint returns clean state.
- **Re-use IntegrationConfig**: Don't create a new DB table per integration — use `integration_id` as the discriminator column.
- **PKCE code_verifier across authorize-callback boundary**: `google-auth-oauthlib >= 1.0` auto-enables PKCE when `authorization_url()` is called. The `code_verifier` is generated and stored only on that `Flow` instance. If the callback creates a *new* `Flow`, the verifier is lost and Google rejects with `(invalid_grant) Missing code verifier`. Solutions:
  - **Confidential clients (have client_secret, preferred)**: Disable PKCE entirely with `flow.autogenerate_code_verifier = False` before calling `authorization_url()`. The callback can then do a direct POST without code_verifier, or use `Flow.fetch_token()` normally.
  - **Public clients (no client_secret)**: PKCE is required. Store `flow.code_verifier` alongside the CSRF state in the authorize step. In the callback, bypass `Flow.fetch_token()` entirely — do a direct POST to the token endpoint with `code_verifier` in the body. See the PKCE Handling section above for both code patterns.
- **Auto-poll race with config panels**: The 5-second `setInterval` in `renderIntCards()` wipes dynamically-inserted config panels if they are open. Suppress auto-poll while any panel is open:
  ```javascript
  setInterval(function() {
    var container = document.getElementById('intCardsContainer');
    var configOpen = false;
    for (var k in EMAIL_CONFIG_OPEN) { if (EMAIL_CONFIG_OPEN[k]) { configOpen = true; break; } }
    for (var k in CONNECTING_IDS) { if (!configOpen) { configOpen = true; break; } }
    if (container && container.innerHTML.length > 0 && !configOpen) {
      renderIntCards();
    }
  }, 5000);
  ```
- **Gmail API: variable assigned in only one code path** — `send_via_gmail_api()` creates the MIME message only inside `if body_html or attachments:`. Plain-text email with no HTML body AND no attachments leaves `msg` unassigned. The subsequent `base64.urlsafe_b64encode(msg.as_bytes()).decode()` crashes with `UnboundLocalError`. Always add an `else` branch:
  ```python
  else:
      msg = MIMEText(body, "plain")
      msg["To"] = to
      msg["Subject"] = subject
  ```
  Same pattern applies to `send_email()` (SMTP path). If you have two send functions, grep for both.
- **Inline onclick escaping in Python triple-quoted strings**: A single backslash before a quote (`\'`) in a Python """...""" string is consumed by Python as an escape for `'`, producing just the quote in the rendered JS — breaking JavaScript syntax. To produce a literal `\'` in the rendered JS (backslash + quote, needed for inline onclick handlers), the Python source must have `\\'` (two backslashes). Python reads `\\` as one literal backslash, then `'` as the quote, yielding `\'` in the string. **Test**: extract the rendered script block and `node --check` it. **Best**: avoid the issue entirely by using event delegation instead of inline `onclick` handlers.
- **JavaScript syntax validation**: After editing the dashboard template, validate the rendered JS:
  ```bash
  curl -s http://localhost:8766/dashboard | python3 -c "
  import sys, re
  html = sys.stdin.read()
  match = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
  open('/tmp/ara_script.js','w').write(match.group(1))
  "
  node --check /tmp/ara_script.js && echo "JS SYNTAX OK"
  ```
  Always verify before restarting the server. A syntax error means the entire script block is dead — no functions are registered, no click handlers work.
- **Gmail OAuth: redirect URI must match GCP console exactly**: The `GOOGLE_REDIRECT_URI` in `app/config.py` (e.g. `https://ara.move78.work/api/integrations/email-gmail/oauth/callback`) MUST be listed in Google Cloud Console → Credentials → OAuth Client → Authorized redirect URIs. If they don't match, Google silently rejects the callback with `redirect_uri_mismatch`. Always add BOTH localhost (for dev) AND production URIs to GCP.
- **Gmail OAuth: env vars required for authorize flow**: `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` must be set in `/opt/ara/.env` (the ARA server's EnvironmentFile). The authorize endpoint checks both and returns `{"error": "Google OAuth not configured"}` if either is empty. Without these, new users can't authorize even if the DB already has valid tokens from a previous session.
- **Gmail OAuth: `google-auth-oauthlib` dependency**: This package is NOT in the base ARA venv. If missing, the authorize endpoint returns HTTP 500 with `ModuleNotFoundError: No module named 'google_auth_oauthlib'`. Install: `pip install google-auth-oauthlib`. All three deps: `google-api-python-client google-auth-oauthlib google-auth-httplib2`.
- **Gmail OAuth: refreshed tokens not persisted to DB** — see `references/email-integration.md` → Token Refresh Persistence section. `send_via_gmail_api()` refreshes in-memory only; every send call re-refreshes from stale DB tokens.
- **Gmail OAuth: diagnosing credential failures** — see `references/oauth-credential-debugging.md`. Directly test client_id/secret against Google's token endpoint to distinguish `invalid_client` (bad credentials / deleted client) from `invalid_grant` (valid credentials, bad token). Critical first step before chasing redirect URIs or env vars.

## Verification Checklist

Before declaring an integration done:
1. Start server, test API: `curl /api/integrations` returns all entries with correct metadata
2. Test connect: `curl -X POST /api/integrations/{id}/connect` returns `config_needed` with field schema
3. Test save-config with bad credentials returns `status: error` with user-friendly message
4. Test status: `curl /api/integrations/{id}/status` returns config data for pre-fill
5. Validate JS syntax with `node --check` (extract script from rendered HTML)
6. **Browser verification** (ARA is an SPA — see `web-browsing` skill's SPA Navigation section):
   - Navigate to dashboard -> click Integrations sidebar link via `browser_console` with `document.querySelector('[onclick*="integrations"]').click()`. **Confirm navigation worked** by checking for integration-specific content:
     ```javascript
     document.body.innerHTML.indexOf('integration-card') > -1 ? 'on integrations page' : 'still on dashboard'
     ```
     If it returns `'still on dashboard'`, the `browser_snapshot` is stale — check via `browser_console` with DOM inspection instead.
   - Verify all integration cards rendered. Use robust selectors by `data-id`, NOT fragile index positions:
     ```javascript
     document.querySelector('[data-id="email-gmail"]')?.textContent?.includes('Gmail') ? 'Gmail card found' : 'missing Gmail'
     document.querySelector('[data-id="email-outlook"]')?.textContent?.includes('Outlook') ? 'Outlook card found' : 'missing Outlook'
     document.querySelector('[data-id="email-smtp-custom"]')?.textContent?.includes('Custom SMTP') ? 'SMTP card found' : 'missing SMTP'
     ```
   - Toggle the integration ON by clicking its data-id checkbox:
     ```javascript
     document.querySelector('[data-id="email-gmail"] input[type="checkbox"]')?.click()
     ```
   - Verify config panel appeared: `document.getElementById('cfg-email-gmail')?.innerHTML?.substring(0, 300)`
   - Verify auto-poll doesn't wipe the config panel (wait 6+ seconds, re-check panel DOM)
   - Toggle OFF via cancel: `cancelEmailConfig('email-gmail')`
   - Verify toggle re-renders to unchecked state (check `input[type="checkbox"]` not checked)
7. Test connecting a real account end-to-end (SMTP test) if possible

## Reference

See `references/email-integration.md` for the concrete Gmail/Outlook/Custom SMTP implementation.
See `references/whatsapp-headless-setup.md` for Playwright headless browser troubleshooting for WhatsApp QR scanning.
