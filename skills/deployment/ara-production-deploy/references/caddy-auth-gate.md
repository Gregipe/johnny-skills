# Caddy Auth Gate (Basic Auth)

## Architecture

Protects the public ARA dashboard behind HTTP basic auth. Caddy (already installed on the server) sits between Cloudflare Tunnel and the ARA server:

```
Cloudflare Tunnel → localhost:8080 (Caddy) → localhost:8766 (FastAPI)
                        ↓
                 Basic auth prompt
```

The sidecar's QR/link page stays accessible without auth via a separate subdomain (`qr.move78.work`).

## One-Time Setup

### 1. Generate password hash

```bash
caddy hash-password --plaintext '<your-password>'
# → $2a$14$O7Cjvp7EluUR95QO555j0OJsA3aFn1hXXfJzOokR8WNYO8UylEK1W
```

### 2. Configure Caddyfile

```bash
cat > /etc/caddy/Caddyfile << 'CADDYEOF'
:8080 {
    basicauth {
        greg $2a$14$O7Cjvp7EluUR95QO555j0OJsA3aFn1hXXfJzOokR8WNYO8UylEK1W
    }
    reverse_proxy localhost:8766
}
CADDYEOF
```

- Caddy listens on **port 8080** (internal, not exposed in UFW)
- Username: `greg` (hardcoded)
- Password: bcrypt-hashed from step 1
- Everything proxied to `localhost:8766` (ARA FastAPI)

### 3. Reload Caddy and update tunnel

```bash
systemctl reload caddy
```

Update the tunnel config to point to Caddy instead of ARA directly:

```yaml
# /root/.cloudflared/config.yml
ingress:
  - hostname: ara.move78.work
    service: http://localhost:8080    # ← Caddy (was localhost:8766)
  - hostname: qr.move78.work
    service: http://localhost:8767    # ← sidecar (unchanged, no auth)
  - service: http_status:404
```

Restart the tunnel:

```bash
systemctl restart ara-tunnel
```

### 4. Verify

```bash
# Without auth → 401
curl -s -o /dev/null -w '%{http_code}' https://ara.move78.work/
# → 401

# With correct password → 200
curl -s -u greg:move78 -o /dev/null -w '%{http_code}' https://ara.move78.work/
# → 200

# Sidecar stays open (no auth)
curl -s -o /dev/null -w '%{http_code}' https://qr.move78.work/status
# → 200
```

## Adding / Removing Users

To add a second user (e.g., for sharing access):

```bash
# 1. Generate hash for the new password
caddy hash-password --plaintext '<friend-password>'

# 2. Add a new basicauth entry
# Edit /etc/caddy/Caddyfile — add another line inside basicauth { }
:8080 {
    basicauth {
        greg $2a$14$...existingHash...
        friend $2a$14$...newHash...
    }
    reverse_proxy localhost:8766
}

# 3. Reload
systemctl reload caddy
```

**To remove a user:** Delete their line from the `basicauth { }` block and reload Caddy. Your own login stays.

## Changing the Password

```bash
# 1. Generate new hash
caddy hash-password --plaintext '<new-password>'

# 2. Edit Caddyfile and replace the hash
# /etc/caddy/Caddyfile — just the hash string, keep same username

# 3. Reload
systemctl reload caddy
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Public URL returns 200 without auth prompt | Tunnel still routing to port 8766 directly | Check `/root/.cloudflared/config.yml` points to `localhost:8080`, then `systemctl restart ara-tunnel` |
| Public URL returns 502 | Caddy on port 8080 is down, or can't reach ARA on 8766 | `systemctl status caddy`, `curl -sf http://localhost:8080/` should return 401 not 502 |
| Auth popup loops (keeps asking for password) | Caddy is behind Cloudflare proxy — Cloudflare doesn't cache 401 | Normal behavior; enter password once per session |
| Can't reach Caddy on port 8080 from localhost | Caddy config might have syntax error | `caddy validate --config /etc/caddy/Caddyfile` |

## Pitfalls

- **Tunnel restart drops all in-flight connections.** After `systemctl restart ara-tunnel`, expect 5-15s of 502/1033 errors before Cloudflare re-establishes. Schedule changes during low-use windows.
- **Caddy already running on port 80/443.** The auth gate uses port 8080 — a DIFFERENT port. The old Caddy config (`:80`) is NOT replaced; it stays serving the default Caddy landing page. Only the `:8080` config serves ARA. If you want to consolidate, you can remove the `:80` block, but there's no harm keeping both.
- **QR subdomain must stay unauthenticated.** The QR/link page on `qr.move78.work` uses `/qr` and `/status` paths that don't need auth. Keeping it on a separate subdomain (`qr.*`) pointing directly to the sidecar (port 8767) avoids adding auth there. Re-authenticating WhatsApp would require re-scanning the QR code.
