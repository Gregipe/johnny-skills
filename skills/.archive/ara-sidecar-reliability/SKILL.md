---
name: ara-sidecar-reliability
description: Sidecar port-conflict prevention, health-check hardening, logging, and watchdog for ARA's WhatsApp Baileys sidecar
---

# ARA Sidecar Reliability

Four fixes applied to `server.py` to prevent silent sidecar outages.

## 1. Explicit-path port killing (`_kill_port`)

`lsof` at `/usr/sbin/lsof` and `fuser` at `/usr/bin/fuser` — launchd's restricted `PATH` may miss these. The function tries explicit paths first, then falls back to bare names:

- Kills PID(s) returned by `lsof -ti:<port>`
- Falls back to `fuser -k <port>/tcp`
- Logs each kill attempt and outcome (previously `except: pass` silently)
- Sleeps 0.5s after kill, then verifies port is free

## 2. Health check verifies WhatsApp connection, not just HTTP 200

Old: `if resp.status == 200: wa._ready = True`

New: `if resp.status == 200 and data.get("connected") is True: ...`

Also verifies **our** `subprocess.Popen` is still alive (`proc.poll() is None`) — catches the case where a leftover old sidecar answers while ours already crashed with EADDRINUSE.

## 3. Visible logging (replaces DEVNULL)

Sidecar stdout/stderr → `logs/sidecar.log` inside the sidecar directory. Helps debug EADDRINUSE, Node crashes, and WhatsApp connection timing.

## 4. Watchdog thread (`_watchdog_sidecar`)

Daemon thread polls every 60s:
- `proc.poll()` — restart if process died
- `/status?connected=true` — restart if WhatsApp disconnected
- `decrypt_error_count` spike detection — restart if zombie connection
- Auto-restores `wa._ready` state

### 4a. Agent Chat Notifications (June 2026)

The watchdog now pushes health notifications into Ava's agent chat via `AgentChatMessage` rows, so Greg sees sidecar status changes in his dashboard without checking logs:

| Event | Message | Timing |
|-------|---------|--------|
| Sidecar disconnects | `⚠️ WhatsApp disconnected (state: awaiting_scan). I'll keep trying to reconnect.` | Immediate |
| Needs QR re-link | `🔴 WhatsApp needs re-linking. Scan the QR code at https://qr.move78.work/link` | After 2 min in `awaiting_scan` |
| Still down | `🟠 WhatsApp still disconnected after 5 minutes. Check the server...` | After 5 min |
| Reconnected | `✅ WhatsApp reconnected — back online.` | Immediate |

Implementation: `_notify_greg_via_chat()` is a nested function inside `_watchdog_sidecar()` that creates `AgentChatMessage` rows directly. Three tracking variables prevent notification spam:
- `_sidecar_down_since` — timestamp when unhealthy state began
- `_sidecar_notified_scan` — QR-scan notification already sent (reset on reconnect)
- `_sidecar_notified_down` — general down notification already sent (reset on reconnect)

### Zombie Connection Detection

The sidecar can be in a state where `connected=true` but all incoming messages fail to decrypt (session keys degraded from frequent restarts). This is a "zombie" — alive on the surface, silently dropping every message.

**Sidecar-side** (`index.js`):
- `decryptErrorCount` variable tracks incoming undecryptable messages
- Incremented in `messages.upsert` when `msg.message` is null and `!msg.key?.fromMe`
- Reset to 0 on every successful `connection === 'open'` event
- Exposed as `decrypt_error_count` in `/status` response

```javascript
// Added alongside other state variables (~line 29)
let decryptErrorCount = 0;

// In connection.update handler, on connection === 'open' (~line 244)
decryptErrorCount = 0;  // Fresh connection = fresh keys

// In messages.upsert handler, before the null-message skip (~line 284)
if (!msg.message) {
  if (!msg.key?.fromMe) decryptErrorCount++;
  continue;
}

// In /status endpoint (~line 605)
decrypt_error_count: decryptErrorCount,
```

**Watchdog-side** (`server.py`):
- Tracks `_last_decrypt_count` between cycles
- If `curr_decrypt - _last_decrypt_count > 10` in a 60s window while `connected=true` → restart
- Threshold of 10 prevents false positives from occasional offline catch-up bursts

```python
# In _watchdog_sidecar() (~line 8078)
curr_decrypt = data.get("decrypt_error_count", 0)
if curr_decrypt - _last_decrypt_count > _DECRYPT_THRESHOLD:
    logger.warning(
        f"Sidecar zombie detected: {curr_decrypt - _last_decrypt_count} "
        f"decryption errors in 60s — restarting"
    )
    wa._ready = False
    _last_decrypt_count = 0
    _start_wa()
    continue
_last_decrypt_count = curr_decrypt
```

## Pitfalls

- **Voice note dedup key uses coarse timestamp (`/ 1000`):** The `contentDedupKey` function (index.js line 73) computes: `${phone}:${text}:${Math.floor(timestamp / 1000)}`. WhatsApp `msg.messageTimestamp` is already in UNIX seconds — dividing by 1000 creates a dedup window of ~16 minutes (1000 seconds). Any two voice notes sent within that window share the same content hash key, so the second is silently dropped by the sidecar with "Voice self-chat skipped (already forwarded)". The fix: for voice notes, use `msg.key.id` directly as the dedup key instead of the timestamp-based hash: `const contentKey = '[voice]' + ':' + (msg.key.id || '');`. This ensures every voice note is treated as unique regardless of send timing. Text message dedup uses the same function but includes the message text in the hash, so only identical texts collide — the `/ 1000` window is still overly coarse for text but less impactful since text messages have unique content.

- **Verification step must use a single path, not the array:** The verification check after killing the port must pass `lsof_paths[0]` (the first candidate path) not `lsof_paths` (the list). `subprocess.run` interprets a list as a program name, not a path plus args — this causes a TypeError at runtime. When patching `_kill_port`, always verify the verification step uses `[lsof_paths[0], "-ti:" + str(port)]`.
- **Double `_start_wa()` call:** The `lifespan` function was starting `_start_wa` **twice** (lines 331 and 337). This caused the second sidecar to always get EADDRINUSE. Removed the duplicate.
- **`subprocess.DEVNULL` makes EADDRINUSE invisible:** Always log sidecar stderr somewhere inspectable.
- **Don't trust `proc.poll()` alone:** A `Popen` can succeed (Node binary started) while the child exits sub-second (EADDRINUSE). The health check must verify the child is still alive after confirming HTTP 200.
- **VPS systemd deployment — sidecar as a separate service:** On a VPS, the sidecar should have its own systemd unit (`ara-whatsapp-sidecar.service`) with the server's unit declaring `Wants=ara-whatsapp-sidecar.service` (NOT `Requires=`). **Critical: `Requires=` causes the server to be killed when the sidecar restarts** — systemd treats `Requires=` as "if this unit stops, stop the requiring unit too." Every sidecar restart would cascade-kill the ARA server. Use `Wants=` so the server stays up independently.

Additionally, the ARA server's scheduler also spawns the sidecar internally via `_start_wa()`. On the VPS, this internal spawn conflicts with systemd's copy. The fix is to use the wrapper.sh approach (see below) so only systemd manages the sidecar lifecycle.

Options: (1) Use `Wants=` + wrapper.sh (recommended), (2) Skip the systemd sidecar unit and let the server manage it entirely (only for single-instance dev setups).

- **Sidecar wrapper.sh pattern (Ubuntu 24.04 / Hetzner):** When the sidecar is run directly via systemd (`ExecStart=/usr/bin/node index.js`), the Node.js process gets killed with SIGKILL (signal 9) after ~76 seconds. **Root cause is EADDRINUSE port conflict from overlapping restarts, NOT an OOM or kernel issue.** Here's the chain:

   1. Something causes the sidecar to exit (WhatsApp disconnect, first-run registration timeout, etc.)
   2. systemd restarts it immediately (`RestartSec=5`)
   3. The old process hasn't fully released port 8767 yet (socket lingering in TIME_WAIT)
   4. The new instance fails with: `Error: listen EADDRINUSE: address already in use :::8767`
   5. Node.js exits with `code=1` — systemd sees "failure" and restarts again
   6. If the old port was released by now, the new instance starts successfully, runs for ~76s, then repeats

   **Fix:** Wrap in a shell script that runs `node index.js &` and `wait`s on it. See `ara-production-deploy` SKILL.md "Sidecar Wrapper" section for the exact wrapper script and systemd config. The wrapper makes signal handling explicit and prevents the port-conflict cascade.

   Without the wrapper, the sidecar restarts 800+ times in under an hour. With the wrapper, it runs indefinitely (verified 25+ minutes stable).

- **Dedup persistence for restart resilience:** The sidecar's in-memory dedup (`forwardedMsgIds` Set) is essential for preventing message doubling but is wiped on every restart. On the VPS, add file-based persistence: save forwarded IDs and content hashes to `/opt/ara/whatsapp-sidecar/dedup_state.json`. Load on startup, save (debounced 5s) on every new forwarded message. This survives restarts and prevents the re-forward cycle.

- **WhatsApp 401 device_removed (server-side kick):** WhatsApp can revoke the linked device session with a stream-level 401 `conflict` error (`type: "device_removed"`). When this happens the sidecar clears auth info and restarts in `awaiting_scan` state — messages sent in the same tick may get msgIds but are not delivered. Symptoms: sidecar suddenly logs out, auth cleared, QR scanning required. The watchdog's agent chat notification will alert Greg within 60s. Recovery: re-scan QR at `https://qr.move78.work/link`. Prevention: none — this is a WhatsApp server-side decision, not a sidecar bug.

- **Sidecar returns false-positive "sent" on corrupted sessions:** The sidecar's `connectionState` stays `"connected"` even when the underlying session has decryption failures (Bad MAC, missing sessions). `sendMessage()` returns a msgId and `{ ok: true }` even when the session cannot deliver. The ARA server trusts this unconditionally. Mitigation: the post-execution sidecar health check in the confirmation flow (see `ara-agent-tools`) now verifies sidecar connectivity after `send_whatsapp` execution and appends a warning ToolResult if the sidecar is unhealthy. Without this, a stale process from a previous restart holds the port and the new instance crashes with EADDRINUSE, triggering an immediate systemd restart loop. Add to wrapper.sh:

```bash
#!/bin/bash
set -e
cd /opt/ara/whatsapp-sidecar

# Kill any zombie process holding port 8767
OLD_PID=$(lsof -ti:8767 2>/dev/null || true)
if [ -n "$OLD_PID" ]; then
  kill -15 "$OLD_PID" 2>/dev/null || true
  sleep 1
  kill -9 "$OLD_PID" 2>/dev/null || true
  sleep 0.5
fi

/usr/bin/node index.js &
NODE_PID=$!
trap 'kill $NODE_PID 2>/dev/null; exit 0' TERM INT
wait $NODE_PID
exit $?
```

This prevents the EADDRINUSE cascade that caused 830+ restarts in under an hour during initial deployment.

## Proven in Practice

During initial deployment, the watchdog caught an EADDRINUSE crash 37 seconds after startup:
```
07:04:16 Sidecar connected to WhatsApp (attempt 1)  ← false positive (old sidecar answering)
07:05:26 Sidecar process died (exit code 1), restarting...  ← watchdog caught it
07:05:29 Sidecar connected to WhatsApp (attempt 4)  ← clean connection
```

The watchdog then kept the new sidecar alive through a subsequent launchd restart (`_kill_port` killed the orphaned old process).

### Real-world resilience (2026-06-05)

Over a ~7 hour runtime, the watchdog handled:
- **2 process crashes** — detected via `proc.poll()` → auto-restarted (exit codes 1 and -9)
- **4 disconnects** — WhatsApp went to `disconnected`/`connecting` state, watchdog waited up to 60s then logged. Some self-healed, some required the crash-restart cycle
- **1 port conflict** — `_kill_port` with explicit paths (`/usr/sbin/lsof`, `/usr/bin/fuser`) killed the orphan from a previous launchd restart

The 60s polling interval meant max downtime was ~60s for any failure mode. For zero-downtime scenarios, reduce to 15-30s.

## 6. Crash-Safe Message Persistence (pending.json)

**Added June 11 2026** — closes the final zero-retry gap in the ARA message pipeline.

### The Pattern

Before forwarding any message to ARA via HTTP POST, the sidecar **synchronously writes** the message to `/opt/ara/whatsapp-sidecar/pending.json`. Only then does it attempt the forward. On crash between write and successful HTTP 200, the message persists in the JSON file and is replayed on next restart.

### Files Changed

`/opt/ara/whatsapp-sidecar/index.js`:

- **`addPending(phone, name, text, ownerReply, msgId, remoteJid)`** — reads current pending list, appends entry with timestamp, writes via `fs.writeFileSync` (synchronous, crash-safe). Deduplicates by msg_id (replaces any existing entry with same msg_id).

- **`removePendingByMsgId(msgId)`** — reads list, filters out matching msg_id, writes back.

- **`sendToARA_promise()` / `sendAudioToARA_promise()`** — Promise-wrapped versions of the old fire-and-forget `sendToARA()`/`sendAudioToARA()`. Resolves `true` on HTTP 200, `false` otherwise. Allows `await` so the calling code can remove pending entries on success.

- **Replay on startup** — inside `startSocket()`, after `loadDedup()` and before normal message processing:
  ```javascript
  const pending = loadPending();
  if (pending.length > 0) {
    logger.info(`Replaying ${pending.length} pending messages from crash recovery`);
    for (const p of pending) {
      const ok = await sendToARA_promise(p.phone, p.name, p.message, ...);
      if (ok) removePendingByMsgId(p.msg_id);
    }
  }
  ```

### Edge Cases Handled

| Scenario | Behavior |
|----------|----------|
| Crash before `fs.writeFileSync` completes | Rare with sync I/O. If it happens, message is lost (same as before fix) |
| Server down during replay | Message stays in pending.json. Retries on next restart |
| Same msg_id arrives via normal path and is also pending | `addPending` deduplicates by msg_id — no double forward |
| Audio messages in pending | Cannot replay (original msg object with stream is gone). Dropped on replay |
| Pending queue grows large | Capped at 1000 entries. Messages older than 1 hour dropped on load |

### Pitfalls

- **Do NOT use async writes** (`fs.writeFile` without Sync) — defeats crash safety. The whole point is that the file is on disk before any network call.
- **Voice notes are still vulnerable** — `addPending` runs for voice too, but `sendAudioToARA_promise` passes through a function that the replay path cannot call (needs the original Baileys message object with audio stream). Replay for voice notes is always rejected. This is acceptable because voice notes are far rarer than text messages and the server-side hallucination + dedup catches most failure modes.
- **pending.json format is an array** — not a JSON object. This keeps `loadPending()` simple: `JSON.parse(fs.readFileSync(...))` returns the array directly.

### Reconnection Message Loss (June 2026)

When WhatsApp forces a session reset, the sidecar disconnects and reconnects. During the ~2-minute reconnection window, messages sent by the user are **permanently lost** — they are NOT saved to pending.json because the sidecar's `messages.upsert` handler isn't running to receive them.

**Symptoms:**
```
Closing open session in favor of incoming prekey bundle
Closing session: SessionEntry { ... }
```
Then ~2 minutes of silence, then retry receipts flood.

**Impact:** Messages sent during this window never reach the server. User sees "sent" in WhatsApp but Ava never responds. This caused Greg's "Yes" to Spectrum deal creation to be silently lost on June 17, 2026.

**Why pending.json doesn't help:** `addPending()` is called inside `messages.upsert` — if the sidecar isn't connected to WhatsApp, it never receives the message, so `addPending()` is never called.

**Mitigation:** Server-side stale-pending detection. If a pending action is `awaiting_approval` for > 5 minutes without a user response, send a nudge: "Still waiting on your confirmation — reply yes/send or ignore."

### Replay Gap: Server Restart vs Sidecar Restart

**Replay only happens on SIDECAR restart**, not server restart. If the server goes down but the sidecar stays up, messages pile up in `pending.json` with no path to delivery. The server has no pull mechanism — it depends entirely on the sidecar to push.

**The gap:** If both server AND user are active but the sidecar hasn't restarted, stale pending messages can sit for hours. Server should have a startup hook that tells the sidecar to flush its pending queue, or the server should poll `pending.json` itself.

**Verified June 17, 2026:** Greg's "Hey Ava - create a lead - Amardeep Shekhawat" sat in pending.json after the server restart. It was only delivered when the sidecar was manually restarted. After delivery, Ava processed it immediately (the `/api/whatsapp/inbound` handler calls `agent_chat()` synchronously).

- `references/disconnect-cycle-2026-06-05.md` — Full disconnect/discovery timeline from a 7-hour runtime window, including the zombie connection incident that motivated the decryptErrorCount detection.
- `references/voice-note-dedup-timestamp-bug.md` — The voice note dedup timestamp collision bug: how `contentDedupKey` divided by 1000 on an already-seconds timestamp, causing voice notes sent within ~16 minutes to be silently dropped, plus the fix and debugging trace.
