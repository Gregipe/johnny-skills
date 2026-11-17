# WhatsApp Sidecar Production Notes (Hetzner / Ubuntu 24.04)

This reference covers production-specific sidecar behavior that differs from local macOS development. See the `whatsapp-sidecar-debugging` standalone skill for general debugging methodology.

## Key Differences from Local Dev

| Aspect | Local (macOS) | Production (Hetzner) |
|--------|---------------|---------------------|
| Process manager | launchd | systemd via wrapper.sh |
| Logging | stderr visible in terminal | journald + wrapper.sh |
| Node direct run | Works indefinitely | Gets SIGKILL after ~76s |
| Dedup | In-memory only | Persisted to dedup_state.json |
| Port conflicts | Rare | Common (zombie processes) |
| ARA server's built-in watchdog | Can coexist | Conflicts — must be disabled |

## SIGKILL Pattern (Hetzner / Ubuntu 24.04 only)

When `node index.js` runs directly as a systemd `Type=exec` process, it receives SIGKILL (signal 9) after approximately 76 seconds. No OOM killer, no error output, no cgroup limits. This is platform-specific — does NOT occur on macOS.

**Fix:** Always use `wrapper.sh` to run the sidecar. The wrapper:
- Kills any zombie process on port 8767 before starting
- Runs `node index.js` as a background child process
- Handles SIGTERM/SIGINT cleanly

**DO NOT** set `ExecStart=/usr/bin/node index.js` in the systemd unit.

## ARA Server's Built-in Watchdog Conflict

The ARA server (`server.py`, around line 8061) has an internal daemon thread `_watchdog_sidecar()` that runs every ~60 seconds. It:
1. Calls `_kill_port(8767)` — kills whatever is on port 8767
2. Starts a bare `node index.js` subprocess via `_start_sidecar()`
3. The bare process dies every ~60s (exit code 0 → no error, no OOM)

**Result:** The watchdog kills our systemd-managed sidecar, then starts a bare one that dies every 60 seconds. The systemd wrapper restarts our sidecar, but the watchdog kills it again.

**Symptoms in logs:**
- Sidecar restart counter in the hundreds
- `journalctl -u ara-server` shows `"Killed PID ... on port 8767"` every 60s
- Sidecar logs show "ARA webhook error" when the server cycles

**Fix:** Disable the watchdog thread. Do NOT remove the function — just stop it from starting:

```python
# In the startup block (around line 337):
# OLD:
# wd_t = threading.Thread(target=_watchdog_sidecar, daemon=True)
# wd_t.start()

# NEW:
# AUTO-MANAGED BY SYSTEMD — sidecar watchdog disabled
pass  # sidecar managed via systemd (wrapper.sh)
```

**Keep `_run_scheduler()` active** — that handles cadences and scheduled actions, not sidecar management.

## Dedup Persistence

The sidecar tracks forwarded message IDs in memory (`forwardedMsgIds` Set). On restart, these are lost, causing message doubling.

**Fix:** A JSON file (`dedup_state.json`) saves the dedup state with a 5-second debounce:

- Reads on startup: `loadDedup()`
- Saves every 5s after a new message is tracked: `saveDedup()`
- Survives any restart: systemd, watchdog, crash

Path: `/opt/ara/whatsapp-sidecar/dedup_state.json`

If the file shows `{"ids":[],"hashes":[]}` during active message processing, the dedup saved before the restart but hasn't seen new messages yet, OR the save timeout hasn't fired yet.

## Port Conflict Prevention (EADDRINUSE)

The sidecar on port 8767 frequently leaves zombie processes. Systemd's `RestartSec=10` is not enough — the old process may linger for seconds after SIGKILL.

**The wrapper handles this:**
```bash
OLD_PID=$(lsof -ti:8767 2>/dev/null || true)
if [ -n "$OLD_PID" ]; then
  kill -15 "$OLD_PID" 2>/dev/null || true
  sleep 1
  kill -9 "$OLD_PID" 2>/dev/null || true
  sleep 0.5
fi
```

This prevents the EADDRINUSE cascade: old process → new process fails → systemd restarts → same port still held → repeat.

## Server-Side Dedup (Belt-and-Suspenders)

Even with persisted sidecar dedup, the ARA server has its own in-memory dedup in `_handle_owner_coach_whatsapp()`:

- `_coach_processed_ids` — tracks message IDs (60s TTL)
- `_coach_processed_hashes` — tracks content hashes (60s TTL)
- `_COACH_RATE_LIMIT` — max 3 coaching responses per 30s per chat

These survive sidecar restarts but NOT ARA server restarts.
