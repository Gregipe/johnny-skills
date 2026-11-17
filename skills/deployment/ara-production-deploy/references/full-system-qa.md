# Full-System QA Checklist

Run this systematic checklist when Greg requests a full stability audit or after significant infrastructure changes. Test every layer in dependency order — don't test the public URL before confirming the server is up locally.

## 1. System Health

```bash
# Load average, uptime
uptime                      # Should be < 1.0 load, ideally < 0.5

# Disk usage
df -h /                     # Should be < 80%

# Memory
free -h                     # Available should be > 500MB

# Top memory consumers
ps aux --sort=-%mem | head -6   # ARA server + sidecar should be #1 and #2
```

## 2. Services

```bash
for s in ara-server ara-whatsapp-sidecar ara-tunnel; do
  printf "%-25s %s\n" "$s:" "$(systemctl is-active $s 2>/dev/null || echo 'not found')"
done
```

Expected: all three `active`.

Check service start timestamps — if any restarted recently, investigate:
```bash
systemctl status ara-whatsapp-sidecar | grep "Active:" | grep -v "ago;"
systemctl status ara-whatsapp-sidecar | grep "restart counter"
```

## 3. Firewall

```bash
ufw status verbose
```

Expected: only ports 22, 80, 443 open. Default: deny incoming.

## 4. Database

```bash
# From /opt/ara
sqlite3 /opt/ara/ara.db "PRAGMA integrity_check;"
# → "ok"

sqlite3 /opt/ara/ara.db "PRAGMA foreign_key_check;" | wc -l
# Should be 0 in ideal state; 500+ orphaned FK refs is non-critical warning
```

## 5. Local Endpoints

```bash
# ARA server
curl -s -o /dev/null -w '%{http_code}' http://localhost:8766/
# → 200

# Sidecar status
curl -s http://localhost:8767/status | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'State: {d[\"state\"]}, Auth: {d[\"authenticated\"]}')"
# → State: connected, Auth: True

# Sidecar health
curl -s http://localhost:8767/health
# → {"status":"ok","uptime":...}
```

## 6. Caddy Auth Gate (if configured)

```bash
# Caddy itself
curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/
# → 401 (auth required)

# Caddy with credentials
curl -s -u greg:move78 -o /dev/null -w '%{http_code}' http://localhost:8080/
# → 200
```

## 7. Public URLs

```bash
# Main dashboard (requires auth)
curl -s -o /dev/null -w '%{http_code}' https://ara.move78.work/
# → 401 (no auth) or 200 (with browser session)

# QR page (no auth)
curl -s -o /dev/null -w '%{http_code}' https://qr.move78.work/status
# → 200
```

## 8. Inbound Webhook (simulate a WhatsApp message)

```bash
curl -s -X POST http://localhost:8766/api/whatsapp/inbound \
  -H 'Content-Type: application/json' \
  -d '{}' -w ' HTTP:%{http_code}'
# → {"status":"skipped","reason":"missing phone or message"} HTTP:200
# (200 means the endpoint is alive and not crashing)
```

## 9. Agent Chat (simulate a coaching request)

```bash
# This tests the full LLM pipeline + prompt format string
curl -s -X POST http://localhost:8766/api/agent/chat/<tenant_id> \
  -H 'Content-Type: application/json' \
  -d '{"message": "hello"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('response') else 'EMPTY')"
# → OK (or "Tenant not found" if tenant_id doesn't exist — still a valid response, not a crash)
```

## 10. Full Restart Test

```bash
# Simulate a reboot scenario
systemctl restart ara-server ara-whatsapp-sidecar ara-tunnel
sleep 10

# Verify all are back
for s in ara-server ara-whatsapp-sidecar ara-tunnel; do
  printf "%-25s %s\n" "$s:" "$(systemctl is-active $s)"
done

# Wait for sidecar to reconnect
for i in $(seq 1 10); do
  sleep 3
  state=$(curl -sf http://localhost:8767/status 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('state','?'))" 2>/dev/null)
  echo "  attempt $i: $state"
  [ "$state" = "connected" ] && break
done
```

## 11. New Reliability Endpoints

```bash
# Thread health — should show running extraction threads
curl -s http://localhost:8766/api/thread-health | python3 -m json.tool

# Error log tail — should be empty or show recent errors
curl -s http://localhost:8766/api/error-log | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d[\"lines\"])} lines')"

# WA queue — should be 0
curl -s http://localhost:8766/api/whatsapp/queue-length
```

## 12. Logs Check

```bash
# Check for errors in the last 100 lines of each service
journalctl -u ara-server --no-pager -n 100 | grep -i "error\|exception\|traceback" | tail -5
journalctl -u ara-whatsapp-sidecar --no-pager -n 100 | grep -i "error\|Killed\|restart counter" | tail -5
journalctl -u ara-tunnel --no-pager -n 100 | grep -i "error\|ERR" | tail -5

# Check error watcher summary
cat /opt/ara/logs/error_summary.log 2>/dev/null | tail -5
```

## What A Healthy System Looks Like

```
ara-server:               active (running since ... 2h ago)
ara-whatsapp-sidecar:     active (running since ... 2h ago) — restart counter = 1
ara-tunnel:               active (running since ... 2h ago)

Firewall: 22/tcp, 80/tcp, 443/tcp only

Sidecar: State: connected, Auth: True

Public URL: 401 (auth required) or 200 (with credentials)
QR subdomain: 200 (no auth)

DB: INTEGRITY: ok
Disk: 11% used
Memory: 3.0GB available
```

## Signals Something is Wrong

| Signal | Likely Issue |
|--------|-------------|
| Sidecar state ≠ "connected" or Auth ≠ True | Auth expired or session corrupted — may need QR re-scan |
| Restart counter > 10 | Port conflict (EADDRINUSE) — kill zombie node process |
| Public URL returns 502 | Tunnel or Caddy down — check both |
| agent_chat returns empty response | Format string crash — check for unescaped curly braces |
| Disk > 80% | Journald growing — `journalctl --vacuum-size=200M` |
| ARA server not responding locally | Systemd may have killed it — check logs for KeyError |
| Sidecar "ARA webhook error" in log | ARA server down or returning 500 — check agent_chat |
