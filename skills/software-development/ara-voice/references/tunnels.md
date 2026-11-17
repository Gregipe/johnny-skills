# HTTPS Tunnel for Meta Webhooks

Meta requires HTTPS for WhatsApp webhook callback URLs. On a bare Hetzner server
(no nginx, no certbot, no domain), here's what works and what doesn't.

## Ngrok (works)

```bash
# Install
apt-get install ngrok

# Authenticate (free account at ngrok.com)
ngrok config add-authtoken <token>

# Tunnel
ngrok http 8768
# → https://xxx.ngrok-free.app
```

Ngrok gives a stable HTTPS URL. Free tier: random subdomain, 1 tunnel, no custom domain.
Callback URL format: `https://xxx.ngrok-free.app/webhook`.

## Cloudflared TryCloudflare (DO NOT USE)

```bash
cloudflared tunnel --url http://localhost:8768
# → https://xxx.trycloudflare.com
```

**Failed 4 out of 4 attempts (July 2026):**
- DNS propagation: hostname not resolvable for 30-60s after tunnel creation
- After DNS resolves: returns 404 even though tunnel is registered and connected
- Tried both QUIC and HTTP/2 protocols, same result
- From both India (BOM edge) and the server itself — 404 or DNS timeout

This might work from other regions or with a Cloudflare account, but the
account-less quick tunnels are unreliable. Wasted 30+ minutes.

## Alternatives (not tested)

- **bore** (`bore local 8768 --to bore.pub`) — plain TCP, no HTTPS, Meta won't accept
- **localhost.run** (`ssh -R 80:localhost:8768 nokey@localhost.run`) — gives HTTPS URL, slow
- **Cloudflare named tunnel** — needs Cloudflare account + domain on Cloudflare. Permanent.

## For Production

Set up nginx + certbot + a domain pointing to the server. Add a reverse proxy
for the voice agent on port 8768. This gives a permanent, stable HTTPS callback URL.
