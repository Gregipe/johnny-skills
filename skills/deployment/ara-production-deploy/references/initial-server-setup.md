# Initial Server Setup (Hetzner CX23)

## Provision

1. Create project + server in Hetzner Cloud Console
2. Settings: CX23, Ubuntu 24.04, Nuremberg (FSN1), SSH key added
3. No volumes, no backups, no firewalls (use UFW on the server)
4. Wait for IP assignment

## First Login

```bash
ssh root@<server-ip>
```

## System Packages

```bash
apt-get update && apt-get upgrade -y
apt-get install -y python3 python3-pip python3-venv nodejs npm git curl ufw build-essential
```

- Python 3.14 ships on Ubuntu 24.04
- Node 22.22 ships on Ubuntu 24.04

## Install Caddy (for HTTPS — optional if using Cloudflare Tunnel)

```bash
apt-get install -y debian-keyring debian-archive-keyring
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt-get update && apt-get install -y caddy
```

## Cloudflare Tunnel

See `references/cloudflare-tunnel-setup.md`. Summary:

```bash
curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared
cloudflared tunnel login  # browser auth — REQUIRED
cloudflared tunnel create ara
```

## Firewall

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

## SSH Key Setup

Generate a deploy key for GitHub access:

```bash
ssh-keygen -t ed25519 -C "ara-server" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```

Add to GitHub → repo → Settings → Deploy keys → **Allow write access** (for DB backup pushes).

Add GitHub to known hosts:

```bash
ssh-keyscan github.com >> ~/.ssh/known_hosts
```

## Git Config

```bash
cd /opt/ara
git config user.email 'gregipe@gmail.com'
git config user.name 'Greg'
```

## Deploy Repo

```bash
cd /opt
git clone git@github.com:Gregipe/ara.git
cd ara
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn sqlalchemy python-dotenv pydantic httpx python-multipart PyMuPDF python-pptx python-docx lxml requests faster-whisper
```

## Hardcoded Path Fixes

The ARA code has hardcoded paths for local dev (`/Users/greg/`). Before deploying, patch:

| File | Change |
|------|--------|
| `server.py` | `load_dotenv` → add fallback paths |
| `server.py` | `UPLOAD_DIR` → `/opt/ara/uploads` |
| `server.py` | `cwd` → `/opt/ara` |
| `database.py` | `db_path` → `/opt/ara/ara.db` |
| `server.py` | `GOOGLE_REDIRECT_URI` → production domain |

**Workflow:** Patch on the server, commit + push to GitHub, pull locally to keep in sync.

## Database Migration

```bash
# From local machine:
scp /Users/greg/ara/ara.db root@<server-ip>:/opt/ara/ara.db

# On server:
mkdir -p /opt/ara/uploads
```

## Systemd Services

Create service files under `/etc/systemd/system/`:

| Service | File | Key Config |
|---------|------|------------|
| ARA Server | `ara-server.service` | `ExecStart=/opt/ara/venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8766` |
| WhatsApp Sidecar | `ara-whatsapp-sidecar.service` | `ExecStart=/opt/ara/whatsapp-sidecar/wrapper.sh` |
| Cloudflare Tunnel | `ara-tunnel.service` | `ExecStart=/usr/local/bin/cloudflared tunnel run ara` |

The sidecar **must** use `wrapper.sh` (not direct node) on Hetzner/Ubuntu 24.04 — running directly causes SIGKILL after ~76s.

```bash
systemctl daemon-reload
systemctl enable --now ara-whatsapp-sidecar
systemctl enable --now ara-server
systemctl enable --now ara-tunnel
```

## Verify

```bash
curl -s -o /dev/null -w '%{http_code}' http://localhost:8766/   # → 200
curl -s http://localhost:8767/status                            # → {...connected: false...}
```

## Deploy Script

`/opt/ara/deploy.sh`:

```bash
#!/bin/bash
set -e
cd /opt/ara
git pull origin main
source venv/bin/activate
pip install -r requirements.txt 2>/dev/null || true
systemctl restart ara-server
echo "Deploy complete."
```
