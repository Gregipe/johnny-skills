# Gmail OAuth Credential Debugging

When the OAuth flow breaks, the critical first step is determining WHICH layer is broken. The Google token endpoint returns different errors for different failures:

## Direct Credential Test

```bash
curl -s -X POST 'https://oauth2.googleapis.com/token' \
  -d 'client_id=YOUR_CLIENT_ID' \
  -d 'client_secret=YOUR_CLIENT_SECRET' \
  -d 'grant_type=refresh_token' \
  -d 'refresh_token=test'
```

## Error Decoder

| Google Response | What It Means | Fix |
|---|---|---|
| `invalid_client` — "The OAuth client was not found" | Client ID/secret pair doesn't exist at Google. Client was deleted, recreated with different secret, or belongs to a different project. | Go to GCP Console → Credentials. If client exists, the secret changed — delete and create a new one. |
| `invalid_grant` — "Bad Request" | Credentials are valid (Google recognized the client), but the refresh token is bogus. **Expected when testing with `refresh_token=test`.** | Credentials work. The actual token refresh/grant depends on the real refresh_token. |
| Success (200 with token) | Everything works. | N/A |

## Why This Matters

- `invalid_client` at the authorize endpoint could be redirect URI mismatch OR bad credentials. The direct token endpoint test isolates credential validity.
- When a client was deleted and recreated in GCP, the `client_id` changes (new OAuth 2.0 Client IDs get new IDs). The old `client_id` in `.env` will fail with `invalid_client`.
- Even if the client ID looks identical in the GCP console, the `client_secret` may have been regenerated. The only reliable check is the token endpoint test.

## Full Debugging Sequence

1. **Test credentials directly** (above) — confirms client exists and secret matches
2. **Check .env vars** — `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` must be set
3. **Check Python deps** — `google-auth-oauthlib` must be installed in venv
4. **Check redirect URI** — Config in GCP must match `GOOGLE_REDIRECT_URI` in `app/config.py`
5. **Verify with local curl** — hit the authorize endpoint and confirm it returns a URL, not an error
6. **Test full OAuth flow** — dashboard → toggle ON → popup → consent → callback
