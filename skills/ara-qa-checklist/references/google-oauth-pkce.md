# Google OAuth PKCE Fix (invalid_grant: Missing Code Verifier)

## Symptom
When connecting Gmail via OAuth popup, Google returns:
```
(invalid_grant) Missing code verifier
```

## Root Cause
`google-auth-oauthlib` v1.4.0 auto-enables PKCE (Proof Key for Code Exchange) on `Flow.authorization_url()` by default. It generates a `code_verifier` (128-char random string) and sends `code_challenge` + `code_challenge_method=S256` in the auth URL.

The problem: the callback endpoint creates a **brand new `Flow` instance** that has no memory of the original `code_verifier`. Google's token endpoint sees a `code_challenge` in the authorization request but no matching `code_verifier` in the token exchange → rejects with `(invalid_grant) Missing code verifier`.

## Fix: Disable PKCE (Confidential Client)

Since ARA uses a **confidential OAuth client** (has `client_secret`), Google does NOT require PKCE. Disable it:

```python
flow = Flow.from_client_config(
    {"web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }},
    scopes=["https://www.googleapis.com/auth/gmail.modify"],
    redirect_uri=GOOGLE_REDIRECT_URI,
)

# KEY LINE: Disable PKCE for confidential client
flow.autogenerate_code_verifier = False

auth_url, state = flow.authorization_url(
    access_type="offline",
    prompt="consent",
    include_granted_scopes="true",
)
```

After disabling, the generated URL will have NO `code_challenge` parameter. Google falls back to standard authorization code flow, which works perfectly with `client_secret`.

## Alternative: Save + Restore code_verifier (If You Need PKCE)

If you're building a **public client** (no client_secret, e.g. mobile/native app), you MUST use PKCE properly:

```python
# Authorize — save code_verifier
auth_url, state = flow.authorization_url(...)
_oauth_states[state] = {
    "created_at": datetime.now(),
    "code_verifier": flow.code_verifier,  # ← SAVE THIS
}

# Callback — restore into new flow
state_data = _oauth_states.pop(state, {})
code_verifier = state_data.get("code_verifier")

# Use direct POST to token endpoint (more reliable than Flow.fetch_token)
import requests
token_data = {
    "code": code,
    "client_id": GOOGLE_CLIENT_ID,
    "client_secret": GOOGLE_CLIENT_SECRET,  # if available
    "redirect_uri": GOOGLE_REDIRECT_URI,
    "grant_type": "authorization_code",
    "code_verifier": code_verifier,  # ← REQUIRED for PKCE
}
resp = requests.post("https://oauth2.googleapis.com/token", data=token_data)
```

## Token Response Normalization

Google's token endpoint returns raw JSON. The format expected by downstream code (e.g. `send_via_gmail_api()`) needs normalization:

```python
tokens = resp.json()
normalized = {
    "access_token": tokens["access_token"],
    "refresh_token": tokens.get("refresh_token"),
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": GOOGLE_CLIENT_ID,
    "client_secret": GOOGLE_CLIENT_SECRET,
    "scopes": tokens.get("scope", "").split(),         # string → list
    "expiry": (datetime.now() + timedelta(
        seconds=tokens.get("expires_in", 3600)
    )).isoformat(),
    "auth_method": "oauth",
}
```

## Verification

1. Call `GET /api/integrations/email-gmail/oauth/authorize` — URL should NOT contain `code_challenge` parameter
2. Popup flow should return `oauth-complete {status: 'connected'}` without errors
3. Check `IntegrationConfig` in DB for tenant — should have `enabled: true` with valid tokens
4. Test sending: `curl -X POST /api/send-test-email` with the stored tokens

## References
- [Google OAuth PKCE](https://developers.google.com/identity/protocols/oauth2/native-app#step1-code-verifier)
- [google-auth-oauthlib source](https://github.com/GoogleCloudPlatform/google-auth-library-python-oauthlib)
- `send_via_gmail_api()` in `email_utils.py` — consumes the normalized token format
