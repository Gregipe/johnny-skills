# Sidecar Debugging Methodology

## The Four-Bug Pattern (Getting WhatsApp Coaching Working)

Setting up owner coaching replies via WhatsApp requires **all four** of these fixes. Missing any one produces a silent failure:

| # | Fix | Layer | Symptom if missing |
|---|-----|-------|--------------------|
| 1 | `emitOwnEvents: true` in Baileys socket opts | Sidecar | Owner replies never trigger `messages.upsert` |
| 2 | `sentMsgIds` echo filter (30s TTL cleanup) | Sidecar | Infinite loop — sidecar re-processes its own sends |
| 3 | `tenant_id=TENANT_ID` on *every* `AgentChatMessage` creation | Server | `IntegrityError` swallowed by generic handler; webhook returns `{"status":"ok"}` but message never saved |
| 4 | `"Ava: "` prefix on all outbound to owner | Server | Owner can't distinguish Ava from human replies |

**Plus** one architectural addition: `chats.update` handler for self-chat detection (see below and `self-chat-limitation.md`).

## Layered Debugging

When WhatsApp replies aren't working, isolate layer by layer. **Never jump to conclusions** — the symptom ("I replied and got nothing") can fail at any layer.

```
Layer 0: Sidecar detects message (two paths)
  ├─ Path A: messages.upsert  (lead replies, owner replies to leads)
  └─ Path B: chats.update     (owner self-chat replies)
Layer 1: Sidecar sends webhook to server (sendToARA helper)
Layer 2: Server webhook handler processes payload
Layer 3: Server saves message to DB
Layer 4: Server calls agent API for response
Layer 5: Agent response sent back to WhatsApp
```

### Layer 0: Sidecar Detection (Dual Path)

### Prerequisite: Sidecar Must Be Logging

Before debugging ANY WhatsApp issue, verify sidecar logs are accessible. The server's `_start_wa()` launches the sidecar with `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL` — zero output captured. Restart the sidecar independently with file logging:

```bash
cd /Users/greg/ara/whatsapp-sidecar
# Kill orphaned sidecars first — find the real PID:
lsof -i :8767 | grep LISTEN
# Kill the node PID (NOT the bash wrapper PID)
kill -9 <node_pid>
# Start with logging
/Users/greg/.hermes/node/bin/node index.js > /tmp/sidecar.log 2>&1
echo $!  # Save this PID for later
```

Note: Hermes `terminal(background=true)` does NOT reliably capture `2>&1` output from background processes. Always redirect to a file (`/tmp/sidecar.log`) when you need to see sidecar logs.

### Marker-Log Pattern (Determining if Events Fire)

When you suspect an event handler is never being called (no custom log lines appear), add a high-visibility marker log at the TOP of the handler BEFORE any filter logic:

```javascript
// Add BEFORE the handler body:
sock.ev.on('messages.upsert', async ({ messages, type }) => {
  logger.info(`[DEBUG] messages.upsert received ${messages.length} messages (type=${type})`);
  for (const msg of messages) {
    logger.info(`[DEBUG] msg key=${JSON.stringify(msg.key)}, fromMe=${msg.key?.fromMe}, hasMessage=${!!msg.message}, remoteJid=${msg.key?.remoteJid}`);
    // ... rest of handler
```

Then redirect sidecar output to a file and grep for the marker:
```bash
cd /Users/greg/ara/whatsapp-sidecar
node index.js > /tmp/sidecar-debug.log 2>&1
# After sending a test message:
grep "\[DEBUG\]" /tmp/sidecar-debug.log | tail -10
```

**What it tells you:**
- `[DEBUG] messages.upsert received 0 messages` — The event fired but had no messages (unusual)
- `[DEBUG] messages.upsert received N messages` plus individual `[DEBUG] msg key=...` lines — The event fires and messages arrive. Debug further down the handler chain.
- Zero `[DEBUG]` lines despite 10,000+ lines of log output — The event NEVER fires. This is the root cause. Likely causes:
  - Baileys can't decrypt any messages (auth corruption — see Auth Corruption section below)
  - `emitOwnEvents: false` suppresses fromMe events
  - Baileys version incompatibility

**Important:** The `[DEBUG]` prefix is grep-friendly. Always use a unique, searchable prefix that won't appear in any library log output.

### Orphan Sidecar Processes

When the ARA server starts the sidecar via `subprocess.Popen`, the node child is NOT in a process group with its bash parent. Killing the bash wrapper (e.g., `kill 59938`) leaves the `node` child alive, holding port 8767. The server's `_start_wa()` checks if a sidecar is already running and skips restart — so the orphan continues running silently.

**Detection**: `ps aux | grep sidecar` shows the bash wrapper PID. The real node process has a different PID and is NOT shown by `grep sidecar`. Use `lsof -i :8767 | grep LISTEN` to find what's actually holding the port.

**Fix**: Kill by the node PID from lsof, not the bash PID from ps:
```bash
lsof -i :8767 | grep LISTEN  # Shows: node  <real_pid>  greg  ... TCP *:8767 (LISTEN)
kill -9 <real_pid>
```

**Prevention**: The server's `_start_wa()` should use `subprocess.Popen(..., start_new_session=True)` to put the sidecar in its own process group, ensuring `kill` on the child propagates correctly. However, this also means the sidecar won't be auto-killed when the server dies (intentional — the sidecar should survive server restarts).

### Auth Corruption — All Messages Fail Decryption

**Symptom:** Sidecar status endpoint returns `{"connected":true,"authenticated":true,"state":"connected"}` but NO messages route to ARA. The sidecar log contains ONLY `"failed to decrypt message"` errors and `"sent retry receipt"` acknowledgments. Zero custom handler log lines (`"Self-chat DM:"`, `"Inbound from"`, `[DEBUG]` markers).

**Root cause:** After repeated restarts or unclean shutdowns, the signal session keys stored in `auth_info/` get corrupted. The sidecar connects to WhatsApp's server and authenticates successfully (the creds are valid), but every message fails E2E decryption because the session cipher state doesn't match what WhatsApp expects. Since no message can be decrypted, `messages.upsert` never fires.

**Detection:**
1. Confirm sidecar is connected: `curl -s http://localhost:8767/status`
2. Check log line count: `wc -l /tmp/sidecar.log` — a few thousand lines in seconds is a red flag
3. Count decryption failures: `grep -c "failed to decrypt message" /tmp/sidecar.log`
4. Count custom handler output: `grep -c "\[DEBUG\]" /tmp/sidecar.log` — should be >0 if debug markers are added
5. If 100% decryption failures with zero handler output → auth corruption

**Fix:** Wipe auth state and re-scan QR code:
```bash
# 1. Kill ALL node processes holding port 8767
lsof -i :8767 | grep LISTEN | awk '{print $2}' | xargs kill -9

# 2. Clear auth info
rm -rf /Users/greg/ara/whatsapp-sidecar/auth_info/*

# 3. Start sidecar fresh
cd /Users/greg/ara/whatsapp-sidecar && node index.js > /tmp/sidecar.log 2>&1 &

# 4. Verify QR code is generated
curl -s http://localhost:8767/status
# → {"connected":false,"authenticated":false,"state":"awaiting_scan","message":"Waiting for QR scan"}

# 5. Open http://localhost:8767/link in browser, scan QR with phone's WhatsApp
# 6. After scan, verify connected:
curl -s http://localhost:8767/status
# → {"connected":true,"authenticated":true,"state":"connected","message":"Authenticated"}
```

**After re-auth:** Expect ~10s of decryption errors for groups created before the auth clear. This is the retry flood settling — new messages decrypt normally.

**Prevention:** Avoid repeated sidecar restarts. Each restart triggers Baileys' offline replay + retry receipt cycle. If you must restart, kill the real node PID via `lsof -i :8767`, not the bash wrapper.

### Detection Paths

The sidecar has two independent detection paths that converge on `sendToARA()`:

**Path A: `messages.upsert`** — handles all normal message types:
- Lead replies to Ava (fromMe=false)
- Owner replies to lead conversations (fromMe=true)
- Fires near-instantly but does NOT catch self-chat messages

**Check**: Look for `"Owner reply to JID"` or `"Inbound from"` in sidecar logs.

**Path B: `chats.update`** — handles self-chat messages:
- Owner replies to "Ava: ..." in self-chat
- Fires within 1-5 seconds (slightly slower than messages.upsert)
- Relies on `chatTimestamps` Map to detect genuinely new messages via timestamp/unreadCount changes

**Check**: Look for `"Self-chat detected via chats.update"` in sidecar logs. If only this log line appears (no webhook response), the issue is in Layer 1+.

**Test**: Isolate by sending a self-chat reply and checking the sidecar stdout:

```bash
# After sending test message, check sidecar output for self-chat detection
# Should show: "Self-chat detected via chats.update: \"test reply...\""
```

**"Ava: " prefix note**: When testing self-chat, you'll receive "Ava: test message" on WhatsApp. Your reply should be the plain message text (e.g., "hello") — the "Ava: " prefix is only applied to outgoing messages, not to your reply.

### Layer 1: Sidecar Reception

**Check**: Does the sidecar log show the inbound message?

```bash
# Reset sidecar output (restart with LOG_LEVEL=info)
LOG_LEVEL=info node index.js

# Look for "Inbound from" or "Owner reply" log lines
```

**Test**: Send a message from a different phone (not the owner's). If THAT doesn't show up either, the connection may be broken.

**If missing**: Check `emitOwnEvents` setting, check if sender is different number (self-chat limitation — see `self-chat-limitation.md`).

### Layer 2: Webhook Delivery

**Check**: Does the server log show the webhook request?

```bash
# Watch server logs
tail -f ~/ara/logs/server.log | grep "whatsapp_inbound"
```

**Test**: Isolate by simulating the sidecar's webhook call with curl:

```bash
# Simulate owner reply to coaching
curl -X POST http://localhost:8766/api/whatsapp/inbound \
  -H "Content-Type: application/json" \
  -d '{"phone":"919582549236","name":"Owner","message":"test reply","owner_reply":true}'

# Simulate lead inbound
curl -X POST http://localhost:8766/api/whatsapp/inbound \
  -H "Content-Type: application/json" \
  -d '{"phone":"919999999999","name":"Test Lead","message":"hello"}'
```

**Expected outcome for coaching reply**: Server logs `_handle_owner_coach_whatsapp` entry, creates/updates coaching thread, returns `{"status":"ok"}`.

### Layer 3: Webhook Handler Logic

**Check**: Does the handler route correctly? Look for routing decisions in the log.

If you get `{"status":"ok"}` but nothing happened in the DB, the exception handler caught an error. **This is the most dangerous failure mode** — the webhook returns success but actually failed.

**Common failures:**
- `IntegrityError` on AgentChatMessage (missing `tenant_id`) — see Pitfall below
- Incorrect owner phone matching (self-vs-other number confusion)
- `_find_lead_by_phone` not matching (wrong digits, @lid JID)

### Layer 4: Database Check

**Test**: Query the coaching thread directly to see if messages exist:

```bash
# Check coaching thread
sqlite3 ~/ara/ara.db "SELECT id, thread_type FROM chat_threads WHERE thread_type='coaching';"

# Check messages in coaching thread
sqlite3 ~/ara/ara.db "SELECT id, role, substring(content, 1, 100), tenant_id FROM agent_chat_messages WHERE thread_id = '<thread_id>' ORDER BY id;"
```

**Key check**: Is `tenant_id` populated on messages? If NULL, the NOT NULL constraint silently ate your message.

### Layer 5: Agent API Response

**Test**: Hit the agent chat API directly to see if Ava responds:

```bash
curl -X POST http://localhost:8766/api/agent/chat/3e736242 \
  -H "Content-Type: application/json" \
  -d '{"message":"test coaching message","thread_id":"<thread_id>"}'
```

### Layer 6: Reply Delivery

**Check**: Did `send_message_sync` return success?

```bash
# Check response logging for "sent" status or msg_id
grep "send_message_sync" ~/ara/logs/server.log
```

## Sidecar Startup: Retry Receipt Flood

When the sidecar reconnects after an extended offline period (hours/days), Baileys triggers `syncFullHistory` and a cascade of retry receipt messages from `messages-recv.js`:

```
{\"msgAttrs\":{\"from\":\"...\",\"type\":\"text\",\"id\":\"...\",\"participant\":\"...\"},\"retryCount\":3,\"msg\":\"sent retry receipt\"}
```

Each message generates a log line. For a heavy chat history, this can produce **thousands of lines** and take 5-10 minutes to settle. During this time, the `messages.upsert` handler is also processing this backlog.

**Debugging implication**: If you restart the sidecar and immediately test, you're fighting through the retry receipt flood. Let the sidecar settle first (watch for ~1 minute of silence in the log output).

**Detection**: Check `process output preview` in Hermes. If the last lines are all retry receipts, it hasn't settled yet.

## Auth Corruption vs. Retry Flood — Key Distinction

| | Retry Receipt Flood | Auth Corruption |
|---|---|---|
| Sidecar status | `connected: true` | `connected: true` |
| Log content | Mix of retry receipts AND some decryption successes | 100% "failed to decrypt" — zero successes |
| Custom handler output | `"Self-chat DM:"` or `"Inbound from"` appears occasionally | NEVER appears |
| Total log lines | Hundreds after settling | Thousands within seconds |
| Fix | Wait for settlement (~2 min) | Wipe auth_info/ and re-scan QR |

## Manual End-to-End Test Sequence

For the fastest debug cycle:

1. **Stop sidecar**: `kill <sidecar_pid>)`
2. **Stop server**: `kill <server_pid>`
3. **Clear DB state** (optional): delete coaching thread from the test tenant
4. **Start server**: watch for healthy startup
5. **Start sidecar**: watch for 'connected' and 'authenticated' log entries
6. **Wait for settlement**: wait until retry receipt flood stops (~2-5 min for busy accounts)
7. **Send test message via sidecar**: `curl -X POST http://localhost:8767/send -d "phone=919582549236&message=Ava: Debug test - reply to check"`
8. **Test webhook directly** (Layer 3-6 isolation): `curl -X POST ...` (see above)
9. **Test webhook via sidecar** (full pipeline): Have someone send a WhatsApp message, or simulate a lead reply

## Common Pitfalls

| Pitfall | Layer | Detection |
|---------|-------|-----------|
| `tenant_id` missing on AgentChatMessage | Layer 3-4 | Message not in DB despite `{"status":"ok"}` response |
| emitOwnEvents: false | Layer 1 | No inbound log entries for ANY fromMe messages |
| Self-chat limitation | Layer 1 | Only fails for owner's own number; lead replies work |
| @lid JID parsing | Layer 2 | Phone extracted from JID is gibberish (not a real number) |
| Sidecar not fully settled | Layer 1 | Don't detect due to processing backlog |
| HTTP server not started | Layer 2 | curl returns connection refused |
| Auth corruption | Layer 0 | 100% "failed to decrypt" with zero handler output |
