# OAuth Credential Rotation on Production

When the Gmail OAuth client is deleted or recreated in Google Cloud Console, the old tokens in `integration_config` become invalid. You must update credentials on the production server.

## Detection

```bash
# Check live status
ssh root@46.224.132.99 'curl -s http://localhost:8766/api/integrations/email-gmail/status'

# If "connected":false and config has old client_id, credentials need rotation
```

## Rotation Steps

### 1. Get new client JSON from Google Cloud Console

The JSON looks like:
```json
{"web":{"client_id":"...apps.googleusercontent.com","project_id":"...","client_secret":"GOCSPX-...","redirect_uris":["https://ara.move78.work/..."]}}
```

### 2. Update integration_config DB on production

```bash
ssh root@46.224.132.99 'cat > /tmp/update_oauth.py << ENDPY
import sqlite3, json
db = sqlite3.connect("/opt/ara/ara.db")
row = db.execute("SELECT config FROM integration_config WHERE integration_id=\"email-gmail\"").fetchone()
config = json.loads(row[0])
config["client_id"] = "NEW_CLIENT_ID.apps.googleusercontent.com"
config["client_secret"] = "NEW_CLIENT_SECRET"
config["access_token"] = ""
config["refresh_token"] = ""
db.execute("UPDATE integration_config SET config=? WHERE integration_id=\"email-gmail\"", (json.dumps(config),))
db.commit()
print("Updated")
db.close()
ENDPY
python3 /tmp/update_oauth.py'
```

### 3. Update .env fallback credentials

```bash
ssh root@46.224.132.99 'cat > /opt/ara/.env << ENVEOF
GOOGLE_CLIENT_ID=NEW_CLIENT_ID.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=NEW_CLIENT_SECRET
ENVEOF'
```

### 4. Ensure redirect URI matches

The `GOOGLE_REDIRECT_URI` in server.py defaults to `https://ara.move78.work/api/integrations/email-gmail/oauth/callback`. This URI must be listed in the Google Cloud Console OAuth client's Authorized Redirect URIs.

### 5. Restart and re-authorize

```bash
ssh root@46.224.132.99 'systemctl kill ara-server; sleep 2; systemctl start ara-server'
```

Then visit `https://ara.move78.work/api/integrations/email-gmail/oauth/authorize` in browser → Google consent → callback populates tokens.

### 6. Verify

```bash
ssh root@46.224.132.99 'curl -s http://localhost:8766/api/integrations/email-gmail/status'
# Should show "connected":true with new access_token
```

## Pitfalls

- **Old tokens survive in the DB**: Just updating client_id doesn't help — old access/refresh tokens are tied to the old client. Clear them to force fresh OAuth flow.
- **`sqlite3` CLI may not exist on server**: Use `python3 -c "import sqlite3"` instead.
- **Caddy basic auth blocks public API calls**: Always test via SSH + localhost:8766, not the public URL, when debugging OAuth.
- **Redirect URI mismatch**: If the URI in Google Console doesn't match `GOOGLE_REDIRECT_URI`, Google returns `redirect_uri_mismatch` after consent.
