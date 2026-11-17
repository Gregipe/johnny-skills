# Gmail OAuth Diagnostics

## Full Diagnostic Script

Run this to check the health of the Gmail OAuth integration:

```bash
cd /Users/greg/ara && venv/bin/python -c "
import json, urllib.request, urllib.parse, urllib.error, sqlite3

db = sqlite3.connect('ara.db')
row = db.execute(\"SELECT config FROM integration_config WHERE integration_id='email-gmail'\").fetchone()

if not row:
    print('❌ No email-gmail integration config found')
    exit(1)

config = json.loads(row[0])
access_token = config.get('access_token', '')
refresh_token = config.get('refresh_token', '')
client_id = config.get('client_id', '')
client_secret = config.get('client_secret', '')

print(f'access_token:  {access_token[:40]}...' if access_token else 'access_token:  MISSING')
print(f'refresh_token: {refresh_token[:40]}...' if refresh_token else 'refresh_token: MISSING')
print(f'client_id:     {client_id[:40]}...' if client_id else 'client_id:     MISSING')
print(f'client_secret: {\"*\" * len(client_secret)}' if client_secret else 'client_secret: MISSING')
print()

# Test 1: Profile check with current access token
print('=== Test 1: Profile check ===')
try:
    req = urllib.request.Request(
        'https://gmail.googleapis.com/gmail/v1/users/me/profile',
        headers={'Authorization': f'Bearer {access_token}'},
    )
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    print(f'✅ Profile OK: {data.get(\"emailAddress\", \"unknown\")}')
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f'❌ HTTP {e.code}: {body[:200]}')
except Exception as e:
    print(f'❌ Error: {e}')

print()

# Test 2: Token refresh
print('=== Test 2: Token refresh ===')
try:
    data = urllib.parse.urlencode({
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    }).encode()
    req = urllib.request.Request(
        'https://oauth2.googleapis.com/token',
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
    )
    resp = urllib.request.urlopen(req, timeout=15)
    fresh = json.loads(resp.read())
    new_token = fresh.get('access_token', '')
    print(f'✅ Token refreshed: {new_token[:40]}...')
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f'❌ HTTP {e.code}: {body[:300]}')

    # Classify the error
    if 'deleted_client' in body:
        print('   → OAuth client was DELETED from Google Cloud Console.')
        print('   → Fix: Create new OAuth client in Google Cloud Console → APIs & Services → Credentials')
        print('   → Then update client_id/client_secret in integration_config and re-run OAuth flow.')
    elif 'invalid_grant' in body:
        if 'Token has been expired or revoked' in body:
            print('   → Refresh token was REVOKED.')
            print('   → Fix: Re-run OAuth authorization flow to get new tokens.')
        else:
            print('   → Invalid grant — refresh token is stale or wrong.')
    elif 'unauthorized_client' in body:
        print('   → Client ID is not authorized for this refresh token.')
        print('   → Fix: The client_id in config doesn not match the one that generated this refresh_token.')
except Exception as e:
    print(f'❌ Error: {e}')

print()

# Test 3: List unread (requires valid token)
print('=== Test 3: List unread messages ===')
try:
    list_url = 'https://gmail.googleapis.com/gmail/v1/users/me/messages?q=is:unread&maxResults=5'
    req = urllib.request.Request(list_url, headers={'Authorization': f'Bearer {access_token}'})
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    msgs = data.get('messages', [])
    print(f'✅ {len(msgs)} unread messages')
    for m in msgs[:3]:
        print(f'   ID: {m[\"id\"]}')
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f'❌ HTTP {e.code}: {body[:200]}')
except Exception as e:
    print(f'❌ Error: {e}')
"
```

## Error Patterns

### `deleted_client`
```
HTTP 401: {
  "error": "deleted_client",
  "error_description": "The OAuth client was deleted."
}
```
**Meaning:** The Google Cloud project's OAuth client ID no longer exists. The `client_id`/`client_secret` pair stored in `integration_config` points to nothing.
**Fix — full re-auth procedure:**
1. Create a new OAuth client ID in Google Cloud Console → APIs & Services → Credentials. Note the `client_id` and `client_secret`.
2. Update the DB config with new credentials, clear old tokens:
   ```bash
   sqlite3 /opt/ara/ara.db "
   UPDATE integration_config
   SET config = json_set(json_set(json_set(json_set(config,
       '$.client_id', 'NEW_ID.apps.googleusercontent.com'),
       '$.client_secret', 'NEW_SECRET'),
       '$.access_token', ''),
       '$.refresh_token', '')
   WHERE integration_id = 'email-gmail';
   "
   ```
3. Update `/opt/ara/.env` with `GOOGLE_CLIENT_ID=...` and `GOOGLE_CLIENT_SECRET=...` (required by the OAuth callback endpoint).
4. Restart server.
5. Open `http://localhost:8766/api/integrations/email-gmail/oauth/authorize` → Google consent → callback stores fresh tokens.
6. Verify: `GET /api/integrations/email-gmail/status` returns `connected: true`.

### `invalid_grant` — Token expired/revoked
```
HTTP 400: {
  "error": "invalid_grant",
  "error_description": "Token has been expired or revoked."
}
```
**Meaning:** The refresh token was manually revoked (user went to Google Account → Security → Third-party apps → Remove access).
**Fix:** Re-run OAuth authorization flow.

### `invalid_grant` — Bad request
```
HTTP 400: {
  "error": "invalid_grant",
  "error_description": "Bad Request"
}
```
**Meaning:** Usually a stale/invalid refresh token. Can happen when the OAuth client was recreated but old tokens kept.
**Fix:** Re-run OAuth authorization flow.

### Access token 401 with valid refresh
```
Profile check: HTTP 401
Token refresh: ✅ OK
```
**Meaning:** Access token expired (normal — they last ~1 hour). The refresh worked, so the poller will auto-refresh.
**Action:** None needed. This is normal operation.

### Both access + refresh dead
```
Profile check: HTTP 401
Token refresh: ❌ (any error above)
```
**Meaning:** Full re-authentication needed. The poller will silently skip until fixed (no crash, just no email processing).
**Fix:** Apply the fix for the specific refresh error, then restart the server.
