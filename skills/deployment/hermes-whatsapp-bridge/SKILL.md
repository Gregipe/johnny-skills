---
name: hermes-whatsapp-bridge
description: "Use when pairing or debugging Hermes WhatsApp bridge."
version: 1.0.0
author: Johnny (Chief of Staff)
platforms: [macos, linux]
license: Proprietary (personal use, Greg)
metadata:
  hermes:
    tags: [whatsapp, baileys, gateway, pairing, hetzner]
    related_skills: [whatsapp-integration, hermes-config-inspection]
---

# Hermes WhatsApp Bridge Ops

## When to Use

- Greg reports WhatsApp comms to Johnny are delayed, missing, or broken.
- Pairing a new bridge device (QR or pairing-code flow), locally or on the
  Hetzner server.
- Operating the remote (server-hosted) bridge: systemd unit, SSH tunnel,
  adapter adoption.

Bridge = `scripts/whatsapp-bridge/bridge.js` (Node/Baileys) exposing an HTTP API
on 127.0.0.1:3000; the gateway's whatsapp adapter
(`plugins/platforms/whatsapp/adapter.py`) long-polls `/messages` and sends via
`/send`. Self-chat mode: only Greg's Message Yourself thread is processed
(`WHATSAPP_ALLOWED_USERS` must include his number or inbound is rejected).

## Debugging "comms not going through"

1. **Gateway log first.** `inbound message: platform=whatsapp` tells you when the
   gateway SAW the message; compare with when Greg sent it. If the gap is minutes,
   the delay happened before the gateway — it's the bridge, not the agent.
2. **Bridge log next** (`profiles/johnny/whatsapp/bridge.log`).
   `Connection closed (reason: 408)` + `Reconnecting in 3s...` followed by many
   minutes of silence while `/health` keeps reporting `connected` = the MAC WAS
   ASLEEP. Confirm with `pmset -g log` (clamshell sleep). TCPKeepAlive holds the
   socket nominally open during sleep, so /health lies; messages are NOT lost —
   they queue and land when the Mac wakes and the bridge reconnects.
   If `/health` instead reports **disconnected** with the same silent log, the
   reconnect loop itself died (socket closed while the machine was awake) —
   kill the bridge process (safe: gateway-managed child; session creds persist,
   no re-pairing needed) and the supervisor respawns it; `/health` flips back to
   connected in ~15s. A "transaction failed, rolling back" burst in bridge.log
   right after respawn is Baileys history-sync noise, not a failure.
3. **Turn latency is separate.** inbound → `Sending response` in gateway.log of
   60–90s is normal (compaction + tools); only the inbound-arrival gap matters.

## Pairing a new device

**QR:** `node bridge.js --pair-json --pair-only --session <dir>` emits JSON lines
`{"event":"qr","qr":"https://wa.me/settings/linked_devices#..."}` (refreshes ~20s).
The bridge's node_modules has only `qrcode-terminal` (ASCII) — render a scannable
PNG with a Swift CoreImage one-liner (`CIQRCodeGenerator` → `NSBitmapImageRep` →
PNG) and `open` it.

**Pairing code:** Baileys `sock.requestPairingCode(phone)` generates the code
computer-side; Greg types it on the phone (Linked devices → Link with phone
number). Phone number without `+`. After registration the socket closes with
401 Unauthorized — EXPECTED: the companion is unauthorized until the phone entry
completes. Requires the account to have two-step verification enabled.

**Half-paired session trap:** `requestPairingCode` sets `creds.me` + `pairingCode`
immediately; re-running against the same session loops `Connection Closed` on
every retry. Wipe the session dir to mint a fresh code.

**Link rate limit:** WhatsApp may refuse linking outright ("can't link devices
now") — transient; wait and retry, or use the pairing-code path instead.

## Remote bridge (server-hosted) — legacy hybrid (superseded by Full server deployment below)

**Adoption gate:** the adapter reuses a running bridge only if /health
`status=connected` AND `scriptHash` equals the hash of the LOCAL bridge.js AND
`sendReadReceipts` matches. Any bridge.js patch must land byte-identically in
the repo copy and the server copy, or the adapter declares the bridge stale and
spawns a local one.

**`remote_bridge` flag:** `platforms.whatsapp.extra.remote_bridge=true` makes the
adapter adopt-or-fail — never spawn, never kill the port. Without it, a gateway
restart during a tunnel outage spawns the local bridge, which then occupies the
tunnel's port forever.

**Deployment layout:** server `/opt/whatsapp-bridge` + systemd
`whatsapp-bridge.service` (self-chat env; `WHATSAPP_REPLY_PREFIX` value contains
spaces and `\n` escapes — the `Environment=` assignment MUST be double-quoted or
systemd rejects it). Mac side: LaunchAgent `ai.hermes.whatsapp-tunnel`
(`ssh -N -L3000:127.0.0.1:3000`, `KeepAlive=true`, `ExitOnForwardFailure=yes`).

**Media:** the bridge serves cached inbound media over `/media/:name` and the
gateway fetches it through the tunnel. Outbound `send-media` (adapter sends a
Mac `filePath` the server bridge cannot read) does NOT work against a remote
bridge — text and inbound media work; outbound media is a known limitation.

**Rollback:** keep the Mac session dir; set `remote_bridge=false` and restart
the gateway → local spawn resumes.

## Cutover order (local → server bridge)

When the server bridge is paired, switch over IN THIS ORDER so the gateway
never wins the race and spawns a local bridge first:

1. Set `platforms.whatsapp.extra.remote_bridge=true` for the johnny profile
   (`hermes config set`), so the next adapter connect() is adopt-or-fail.
2. Stop the local bridge process (gateway-managed child; killing it is safe —
   the tunnel takes the port).
3. Load the tunnel: `launchctl load ~/Library/LaunchAgents/ai.hermes.whatsapp-tunnel`.
4. Verify `curl http://127.0.0.1:3000/health` now reports the SERVER bridge
   (uptime resets, same scriptHash as the local repo file).
5. Restart the gateway; gateway.log must show
   `Using existing bridge (status: connected)` — not `Bridge started on port`.
6. End-to-end: POST /send a message prefixed with WHATSAPP_REPLY_PREFIX to the
   self-chat lid (prefix makes the bridge ignore it as an agent echo) and
   confirm it lands; then have Greg send an inbound ping and confirm a reply.

A ready pairing-code script (`node pair_code.mjs <session-dir> <phone>`,
prints `PAIRING_CODE=...` and keeps the socket alive for the link to
complete) is in `scripts/pair_code.mjs` — deploy it to the server before use.

## Cron delivery to WhatsApp

Cron jobs delivering to WhatsApp need an EXPLICIT target — bare `deliver='whatsapp'`
fails with "no delivery target resolved" because self-chat mode registers no home
channel (unlike Telegram's `TELEGRAM_HOME_CHANNEL`). Use the LID form:
`deliver='whatsapp:<lid>'` — Greg's Message Yourself thread LID is
`37039848317007@lid` (also the `platforms.whatsapp.channel_overrides` key in
config.yaml). `to_whatsapp_jid()` passes `@lid` values through untouched, so the
LID is bridge-safe. No `:thread_id` segment — the self-chat thread IS the main
chat. `attach_to_session: true` makes briefings replyable in-thread.

After creating or changing a job's deliver target, TEST-FIRE it before trusting
it (`cronjob_manage action='run'`; the run prompt flags the output as a test) and
confirm against the authoritative record: `sqlite3 <profile>/cron/executions.db
"SELECT status, delivery_outcome, error FROM executions WHERE job_id='<id>'
ORDER BY claimed_at DESC LIMIT 1"` → expect `delivery_outcome='delivered'`.
gateway.log "Sending response" lines are the turn path, not cron delivery, and
the bridge may not log successful sends at all — log silence proves nothing;
only the executions.db outcome distinguishes delivered from failed.

## Full server deployment (gateway + bridge on the VPS)

Topology when Johnny must stay reachable while the Mac is asleep or dead:
gateway + WhatsApp bridge + cron + dashboard all run on the Hetzner VPS under
systemd; the Mac becomes a client (browser dashboard / SSH). No tunnel needed
when bridge and gateway share the box.

- **Install:** `git clone` the repo on the server, then
  `bash scripts/install.sh --dir <checkout> --non-interactive`. The installer
  auto-fetches the latest stable release, which may differ from the Mac's
  commit — check `git merge-base --is-ancestor <mac-commit> <release-tag>`:
  if the Mac commit is an ancestor, the newer release migrates config forward
  and needs no re-pin; otherwise re-run the installer with `--commit`.
- **Long server commands die with the ssh channel** — a dropped connection
  resets the remote command tree. Run installs with
  `nohup ... > /tmp/<name>.log 2>&1 &` and re-check via the log.
- **Session:** copy the MAC's actively-connected `whatsapp/session` into the
  server profile at cutover. Idle server-side sessions go stale ("Logged out.
  Delete session and restart to re-authenticate") and are unrecoverable
  without re-pairing. One active socket per session — stop the Mac bridge
  before the server one starts.
- **Adoption gate is machine-local:** the running bridge's `scriptHash` is
  compared against THAT install's repo copy of bridge.js, so internal
  consistency is automatic; cross-machine parity only matters for the
  remote_bridge hybrid.
- **Profile transfer manifest:** config.yaml, .env, auth.json, skills/,
  memories/, cron/, whatsapp/session. EXCLUDE heavy runtime dirs: state.db,
  sessions/, home/, logs/, bin/, caches. Then remap Mac paths inside
  cron/jobs.json (e.g. /Users/greg/johnny-dashboard → /root/johnny-dashboard).
- **Dashboard:** rsync `~/johnny-dashboard` to the server, add a Caddy site
  with basic-auth (same pattern as ARA's :8080 site), and patch bridge.py CORS
  to allow the Caddy origin (it allows only the 8410 origin by default).
- **Cutover order:** launchd `bootout` removes the job but does NOT stop the
  running gateway — the process must be killed separately, and Greg gates that
  kill explicitly. Get the go-ahead, then: stop Mac gateway+bridge → rsync
  manifest + session → start the server gateway (it spawns its own bridge) →
  verify gateway.log shows `✓ whatsapp connected` and `✓ telegram connected` →
  test-fire a WhatsApp cron. Exactly ONE gateway per profile ever — never run
  Mac and server gateways for the same profile at once (double cron ticks,
  Telegram poller conflict, WhatsApp session clash).
- **Rollback:** the Mac profile stays intact (session is copied, not moved);
  stop the server gateway, restart the Mac gateway, and the old topology
  resumes.

## Inbound voice notes failing auto-transcription

When a voice note arrives flagged "could not be transcribed automatically",
transcribe it yourself with the verified pipeline in
`references/voice-note-manual-transcription.md` (ffmpeg to 16kHz mono WAV →
`/opt/ara/scribe_stt.py`, Scribe v2). Returns in seconds; then reply to Greg
from the transcript.

## Pitfalls

- `pkill -f <pattern>` inside an ssh one-liner matches the remote shell's OWN
  cmdline (the command text contains the pattern) and kills the session before
  the rest of the chain runs. Exclude the shell: `PIDS=$(pgrep -f <pattern> |
  grep -v "^$$$")`, then kill by PID.
- `Poll error: Cannot connect to host 127.0.0.1:3000` in gateway.error.log =
  the bridge process is down (Mac asleep or crash), not a gateway config issue.
