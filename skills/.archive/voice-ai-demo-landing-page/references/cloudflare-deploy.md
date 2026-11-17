# Deploying the Demo to Cloudflare Workers (production URL)

Local `wrangler dev` proves the app works, but a client pitch needs a shareable
`*.workers.dev` URL (which also sidesteps any localhost/browser-specific network
weirdness). This is the exact sequence that worked for Mondelez.

## 1. Auth (wrangler login)

```bash
cd ~/<client>-voice-ai
npx --yes wrangler login   # NO CI=1, run with pty so you can see the URL
```

**Two gotchas that both bite:**

- **`CI=1` breaks the login.** In CI mode wrangler does not open the browser and
  the process exits with code 1 and *no output*. Do NOT prefix `CI=1`. Run it in a
  pty (`terminal(pty=true)`) so the OAuth URL is visible in the log.
- **Never re-paste a truncated OAuth URL.** If the browser window doesn't open
  automatically and you copy the `https://dash.cloudflare.com/oauth2/auth?...` URL
  into chat for the user, the full URL includes a long `state` AND a
  `code_challenge` (PKCE) param. Truncating either → `OAuth error: invalid_state`
  on the callback. The correct fix is to tell the user to click **Allow in the
  window wrangler opens itself**, not any URL you hand them.

Confirm with `npx --yes wrangler whoami` (prints the account email).

## 2. Bind the Hunar key as a Worker secret

Secrets live on the deployed Worker, not in `.dev.vars`. Pipe the value in via
stdin (don't echo it):

```bash
KEY=$(grep '^HUNAR_API_KEY=' .dev.vars | cut -d= -f2- | tr -d '"')
printf '%s' "$KEY" | CI=1 npx --yes wrangler secret put HUNAR_API_KEY
```

(`GOOGLE_SERVICE_ACCOUNT_JSON` can be skipped if the client hasn't supplied a real
one — call logging silently 500s in the console, the demo still works.)

## 3. Deploy

```bash
CI=1 npx --yes wrangler deploy
```

Output gives the URL: `https://<worker-name>.<subdomain>.workers.dev`. The worker
name comes from `wrangler.jsonc` `name`; the subdomain is the account's
`*.workers.dev` subdomain (visible after login in whoami / deploy output).

## 4. Verify production WITHOUT firing a call

```bash
U="https://<worker-name>.<subdomain>.workers.dev"
curl -s "$U/"                                   # page HTML: new UUID, custom_data, lang
curl -s "$U/api/calls/bogus123" -w '\n%{http_code}'   # read-only auth probe
```

A `422 {"message":"Validation Failed for fields: call_id", ...}` from the last
call proves the bound `HUNAR_API_KEY` is authenticating against Hunar in prod —
if the secret were missing/mismatched it would return `401 Invalid API key`. This
is the same "read the JSON error" discipline as local debugging, just against the
public URL.

## Post-deploy notes

- The URL is **public**: anyone with it can trigger calls to any number on the
  client's Hunar billing. Fine for a handed-out pitch; offer an allowlist gate if
  it might leak.
- Free Workers tier (100K req/day) is far beyond demo needs.
