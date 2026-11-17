# Gmail OAuth Setup Verification Checklist

When email cadence steps fail with "Gmail API error," verify these in order:

## 1. Environment Variables (.env)

Check `/opt/ara/.env` for:
```
GOOGLE_CLIENT_ID=<client_id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-<secret>
```

The authorize endpoint at `/api/integrations/email-gmail/oauth/authorize` reads these from `app/config.py` via `os.getenv()`. Without them, the endpoint returns `{"error": "Google OAuth not configured."}`.

## 2. Redirect URI Must Match Google Cloud Console

The hardcoded redirect URI in `app/config.py`:
```
GOOGLE_REDIRECT_URI = "https://ara.move78.work/api/integrations/email-gmail/oauth/callback"
```

This EXACT string must be listed in **Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID → Authorized redirect URIs**. Google strictly matches redirect URIs — any mismatch triggers `invalid_client`.

## 3. Client ID + Secret Validity

Test directly against Google's token endpoint:
```bash
curl -s -X POST 'https://oauth2.googleapis.com/token' \
  -d "client_id=$GOOGLE_CLIENT_ID" \
  -d "client_secret=$GOOGLE_CLIENT_SECRET" \
  -d 'grant_type=refresh_token' \
  -d 'refresh_token=test'
```

- `invalid_client` / "The OAuth client was not found" → client ID doesn't exist or secret is wrong (regenerated in console)
- `invalid_grant` / "Bad Request" → client is valid, just the test refresh token is fake (expected)

## 4. Required Python Packages

Two separate packages are needed, installed in the ARA venv:

```bash
/opt/ara/venv/bin/pip install google-auth-oauthlib google-api-python-client
```

| Package | Used by | Missing symptom |
|---------|---------|-----------------|
| `google-auth-oauthlib` | OAuth authorize endpoint (`from google_auth_oauthlib.flow import Flow`) | `ModuleNotFoundError: No module named 'google_auth_oauthlib'` → 500 on authorize |
| `google-api-python-client` | `send_via_gmail_api` (`from googleapiclient.discovery import build`) | `Gmail API error: No module named 'googleapiclient'` → email send fails |

**Note:** `google-auth-oauthlib` was NOT in the original requirements. It's a separate dependency from `google-auth` and must be installed explicitly.

## 5. DB Token Verification

After OAuth flow completes, check stored tokens:
```sql
SELECT config FROM integration_config WHERE integration_id = 'email-gmail';
```

Tokens should contain: `access_token`, `refresh_token`, `client_id`, `client_secret`, `expiry`, `scopes`. Expired tokens auto-refresh via `send_via_gmail_api` → `creds.refresh(Request())`.

## 6. Server Restart Required

After adding env vars or installing packages: `systemctl restart ara-server`
