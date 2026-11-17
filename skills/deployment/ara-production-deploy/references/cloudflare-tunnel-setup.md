# Cloudflare Named Tunnel Setup

## Prerequisites
- Cloudflare account with at least one domain
- Domain's nameservers pointing to Cloudflare (NS propagation can take min-hours)
- Server already provisioned and SSH-accessible

## One-Time Auth

Named tunnels require the origin certificate (`~/.cloudflared/cert.pem`). An API token **will not work** — `cloudflared tunnel create` errors with:

```
Cannot determine default origin certificate path. No file cert.pem in [...]
```

**Do this once per server:**

```bash
cloudflared tunnel login
```

This opens a URL. Visit it in a browser, select your domain, authorize. Creates `~/.cloudflared/cert.pem`.

## Create the Tunnel

```bash
cloudflared tunnel create ara  # or whatever name
```

Output:
```
Tunnel credentials written to /root/.cloudflared/<uuid>.json.
Created tunnel ara with id <uuid>
```

Keep the UUID — you need it for the config file.

## Configure Ingress

`~/.cloudflared/config.yml`:

```yaml
tunnel: <uuid>
credentials-file: /root/.cloudflared/<uuid>.json

ingress:
  - hostname: ara.yourdomain.com
    service: http://localhost:8766
  - hostname: qr.yourdomain.com         # separate subdomain for sidecar
    service: http://localhost:8767
  - service: http_status:404
```

### Subdomain Routing vs Path-Based Routing

**Use subdomain routing.** Path-based routing (`/qr*` → port 8767) was tried first and was unreliable:

| Approach | Reliability | Notes |
|----------|------------|-------|
| Subdomain (`qr.move78.work` → 8767) | ✅ Reliable | Clean routing, JS fetch works on same origin |
| Path-based (`/qr*` → 8767) | ❌ Flaky | Returns 502/1033 errors intermittently |

The path-based approach fails because the QR page's JavaScript fetches `/qr` on the **same origin** as the page. If that origin routes to the ARA server (port 8766) instead of the sidecar (port 8767), the fetch returns 404 — the QR never loads.

## Route DNS

```bash
cloudflared tunnel route dns ara ara.yourdomain.com
cloudflared tunnel route dns ara qr.yourdomain.com
```

Creates CNAME records automatically. Propagation is usually instant through Cloudflare.

## Systemd Service

```ini
[Unit]
Description=Cloudflare Tunnel — ara.yourdomain.com
After=network.target your-app.service
Wants=network.target
Requires=your-app.service

[Service]
Type=simple
ExecStart=/usr/local/bin/cloudflared tunnel run ara
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now ara-tunnel
```

## Verify

```bash
curl -s -o /dev/null -w '%{http_code}' https://ara.yourdomain.com/
# → 200

curl -s -o /dev/null -w '%{http_code}' https://qr.yourdomain.com/status
# → 200
```

## Pitfalls

### 502 After Restart
On `systemctl restart ara-tunnel`, Cloudflare returns 502 for 5-15s while the tunnel re-establishes. Normal. Wait 15s and retry.

### Quick Tunnel Rate Limiting
The ephemeral quick tunnel (`cloudflared tunnel --url http://localhost:8766`) has no uptime guarantee and returns `429 Too Many Requests` if restarted too often. Stop the service and wait 2-3 minutes. Use a named tunnel for production.

### Worker.dev Subdomain Won't Work
Cloudflare Workers subdomains (`*.workers.dev`) cannot route tunnel traffic directly. You need a real domain (any cheap `.work`, `.in`, `.xyz` domain works — ₹79-₹199/year).

### DNS Propagation for New Subdomains
If you add a new subdomain (e.g., `qr.move78.work`) and curl returns `000` (could not resolve), DNS hasn't propagated yet. Wait 30-60s, or check with `dig +short qr.move78.work @1.1.1.1`.
