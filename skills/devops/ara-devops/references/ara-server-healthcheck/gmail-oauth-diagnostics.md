# Gmail OAuth Diagnostics

## Quick Token Health Check

```bash
cd /Users/greg/ara && venv/bin/python -c "
import json, sqlite3, urllib.request, urllib.error

db = sqlite3.connect('/opt/ara/ara.db')
row = db.execute(\"SELECT config FROM integration_config WHERE integration_id='email-gmail'\").fetchone()
if not row:
    print('No Gmail integration configured')
    exit(1)

config = json.loads(row[0])
token = config.get('access_token', '')
print(f'Access token present: {bool(token)}')
print(f'Access token prefix: {token[:30]}...')

# Test the access token
req = urllib.request.Request(
    'https://gmail.googleapis.com/gmail/v1/users/me/profile',
    headers={'Authorization': f'Bearer {token}'},
)
try:
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    print(f'✅ Token valid — connected as: {data.get(\"emailAddress\", \"unknown\")}')
except urllib.error.HTTPError as e:
    body = e.read().decode()
    if 'deleted_client' in body:
        print('❌ OAuth client was DELETED — create a new one in Google Cloud Console')
    elif 'invalid_grant' in body:
        print('❌ Refresh token invalid_grant — re-authenticate')
    elif 'expired' in body.lower():
        print('⚠️ Token expired — attempting refresh...')
    else:
        print(f'❌ HTTP {e.code}: {body[:200]}')
except Exception as e:
    print(f'❌ Connection error: {e}')
"
```

## Refresh Token Test

If the access token is expired, test the refresh token:

```bash
cd /Users/greg/ara && venv/bin/python -c "
import json, sqlite3, urllib.request, urllib.parse

db = sqlite3.connect('/opt/ara/ara.db')
row = db.execute(\"SELECT config FROM integration_config WHERE integration_id='email-gmail'\").fetchone()
config = json.loads(row[0])

refresh = config.get('refresh_token')
client_id = config.get('client_id', '')
client_secret = config.get('client_secret', '')

print(f'refresh_token: {bool(refresh)}')
print(f'client_id: {bool(client_id)}')
print(f'client_secret: {bool(client_secret)}')

if not all([refresh, client_id, client_secret]):
    print('Missing OAuth credentials — re-authenticate')
    exit(1)

data = urllib.parse.urlencode({
    'client_id': client_id,
    'client_secret': client_secret,
    'refresh_token': refresh,
    'grant_type': 'refresh_token',
}).encode()

req = urllib.request.Request(
    'https://oauth2.googleapis.com/token',
    data=data,
    headers={'Content-Type': 'application/x-www-form-urlencoded'},
)

try:
    resp = urllib.request.urlopen(req, timeout=15)
    body = json.loads(resp.read())
    print(f'✅ Refresh succeeded — new token: {body.get(\"access_token\",\"\")[:30]}...')
except urllib.error.HTTPError as e:
    body = e.read().decode()
    error_type = json.loads(body).get('error', 'unknown')
    if error_type == 'deleted_client':
        print('❌ OAuth client was DELETED from Google Cloud Console')
        print('   Go to https://console.cloud.google.com/apis/credentials')
        print('   Create a new OAuth 2.0 Client ID (Web application)')
        print('   Set redirect URI: https://ara.move78.work/api/integrations/email-gmail/oauth/callback')
        print('   Then re-auth at /api/integrations/email-gmail/oauth/callback')
    elif error_type == 'invalid_grant':
        print('❌ Refresh token invalid — user revoked access or token expired (>6 months unused)')
        print('   Re-authenticate via OAuth flow')
    else:
        print(f'❌ Refresh failed: {error_type} — {body[:300]}')
"
```

## Integration Status from API

```bash
curl -s http://localhost:8766/api/integrations | python3 -c "
import sys, json
items = json.load(sys.stdin)
for i in items:
    if 'email' in i.get('type',''):
        print(f'Type: {i[\"type\"]}')
        print(f'Enabled: {i.get(\"enabled\")}')
        print(f'Connected: {i.get(\"connected\")}')
"
```

## Common Failure Modes

| Error | Meaning | Fix |
|-------|---------|-----|
| `deleted_client` | OAuth client ID removed from Google Cloud | Create new OAuth client, re-auth |
| `invalid_grant` | Refresh token revoked or expired | Re-authenticate OAuth |
| `401` + "invalid authentication" | Access token expired AND refresh failed | Re-authenticate OAuth |
| `enabled=True, connected=False` | Integration config exists but auth is dead | Run diagnostics above |
| `[]` tenants, all zeros | Server looking at wrong DB | Check `/opt/ara/ara.db` exists |

## The `/opt/ara` macOS Trap

On macOS development, `/opt/ara` does not exist. The server hardcodes this path for:
- Database: `/opt/ara/ara.db`
- Uploads: `/opt/ara/uploads/`
- Env: `/opt/ara/.env`

When the server starts without `/opt/ara`:
1. `os.makedirs('/opt/ara/uploads')` crashes if `/opt` is root-owned (macOS) → PermissionError
2. If `/opt/ara` exists but `ara.db` doesn't → SQLAlchemy creates a fresh empty DB
3. The fresh DB has zero tenants/leads/deals → API returns empty arrays
4. The real data at `/Users/greg/ara/ara.db` is ignored
5. Symptom: 200 OK on `/` and `/dashboard`, but all data endpoints return empty

**Always verify:** `sqlite3 /opt/ara/ara.db "SELECT count(*) FROM leads;"` matches the expected count.
