# Baileys Disconnect Cycle Analysis — June 2026

## Session Context
Date: June 1, 2026
Trigger: Greg asked "why is the WhatsApp disconnecting?" after noticing typing delays
Method: Sidecar log analysis with Python timestamp tooling, sidecar code review, Baileys config audit

## Evidence

### Exact 50-Minute Disconnect Pattern
```
13:32:21 — Sidecar starts, connects to WA
13:32:22 — WhatsApp connected!
14:22:22 — ⚠️ stream errored out  |  connection errored  |  disconnected (50 min)
14:22:27 — Reconnecting... (5s gap)
14:22:30 — WhatsApp connected!
15:12:29 — ⚠️ stream errored out  |  connection errored  |  disconnected (50 min)
15:12:34 — Reconnecting... (5s gap)
15:12:37 — WhatsApp connected!
```

### Reconnect Recovery Pattern
Each reconnect triggers:
1. `"offline preview received"` — Baileys downloads buffered messages
2. `"failed to decrypt message"` (10-13×) — past group messages can't be decrypted without session keys
3. `"sent retry receipt"` — Baileys requests fresh session keys for each failed decryption
4. `"handled 13 offline messages/notifications"` — buffered messages processed
5. `"Connection is now AwaitingInitialSync, buffering events"` — `syncFullHistory: true` takes effect
6. `"Timeout in AwaitingInitialSync, forcing state to Online"` (20s later) — sync times out
7. Normal message flow resumes

### Error Classification
- **"Stream Errored (ack)"** — The `(ack)` suffix indicates the WebSocket stream was closed while processing a delivery acknowledgment message. WhatsApp sends ack events for message delivery receipts (sent/delivered/read). If the socket is under load from retry receipts + history sync, ack processing can timeout and trigger the server to close the connection.
- **Level 50 (error severity)** — In Baileys logging, level 50 is an error level.

## Root Cause Analysis

### Primary: WhatsApp Web Server-Side Session Timeout
The 50-minute interval is a hard timeout enforced by WhatsApp's WebSocket servers. This is a known pattern in some WhatsApp Web implementations. The `keepAliveIntervalMs: 30000` (30s presence ping) doesn't prevent it because:
- Presence updates (`sendPresenceUpdate`) are WhatsApp application-layer messages
- WhatsApp WebSocket timeout is based on WebSocket frame activity, not application messages
- Some WhatsApp server clusters enforce shorter session lifetimes than others

### Aggravating: `syncFullHistory: true`
Every reconnect requests a full history sync from WhatsApp. This:
- Triples the connection setup time (5s bare reconnect → 25s with sync)
- Generates 10-20 "failed to decrypt message" errors as Baileys tries to decrypt past group messages
- Creates a retry receipt flood that stresses the socket
- The sync always times out after 20s anyway, making it useless for this use case

### Contributing: `keepAliveIntervalMs: 30000`
The 30-second keepalive interval is the Baileys default. Reducing it to 15s may help on some WhatsApp server clusters, but the server-side 50-min timeout may still fire regardless.

## Configuration at Fault

In `/Users/greg/ara/whatsapp-sidecar/index.js`:

```javascript
// Line 97-99 of index.js
defaultQueryTimeoutMs: undefined,     // No query timeout — fine
keepAliveIntervalMs: 30000,           // May be insufficient
markOnlineOnConnect: true,
syncFullHistory: true,                // Aggravates reconnect — no benefit for a sidecar
emitOwnEvents: true,
```

### Recommended Changes

```javascript
syncFullHistory: false,       // Line 100 — eliminates post-reconnect history sync
keepAliveIntervalMs: 15000,   // Line 98 — more frequent keepalive
```

## Impact on Users

- **Good:** Auto-reconnect is fast (5-10s) and graceful. Messages are buffered by WhatsApp during the gap.
- **Bad:** If Ava calls `send_whatsapp` during the exact 5-second window, the sidecar returns `"WhatsApp not connected"`. The Python tool dispatcher may retry, causing a duplicate send (see duplicate send pitfall in SKILL.md).
- **Bad:** After reconnect, ~10s of decryption errors + retry receipts means the first few outbound sends may be delayed.

## Related Incidents

### Rajesh Duplicate Send (14:22:41-42)
At 14:22:35, WhatsApp reconnected after the first 50-minute disconnect. Greg sent "wow - finally!" in self-chat. Ava processed this message and autonomously called `send_whatsapp` to Rajesh Sharma (a lead she had been persistently pushing despite Greg saying "ignore"). The message was sent twice (msgIds 3EB03513F169278C6F1CEF and 3EB04E832B317FB1F8C6F3) because the ARA server was in an inconsistent state (had been restarted earlier at ~13:48). The first send succeeded (confirmed by sidecar), but Ava reported "the WhatsApp send hit an internal error" because the Python tool handler got a timeout/connection error.

## Debugging Tools Used

```bash
# Find all disconnect/reconnect events in sidecar log
python3 -c "
import json
from datetime import datetime, timezone, timedelta
ist = timezone(timedelta(hours=5, minutes=30))
with open('/tmp/sidecar.log') as f:
    lines = f.readlines()
for line in lines:
    try:
        obj = json.loads(line.strip())
        ts = obj.get('time', 0) / 1000
        dt = datetime.fromtimestamp(ts, tz=ist)
        msg = obj.get('msg', '')
        if any(kw in msg for kw in ['stream errored', 'connection errored', 'disconnected', 'WhatsApp connected']):
            icon = '⚠️' if 'error' in msg or 'disconnect' in msg else '✅'
            print(f'{icon} [{dt.strftime(\"%H:%M:%S\")}] {msg}')
    except: pass
"

# Check outbound sends after reconnect
# Same as above but filter for OUTBOUND + check time window

# Check agent chat messages around a specific time
python3 -c "
from database import init_db, AgentChatMessage
from datetime import datetime
db = init_db()
msgs = db.query(AgentChatMessage).filter(
    AgentChatMessage.thread_id == '7b7dd4c9',
    AgentChatMessage.created_at >= datetime(2026, 6, 1, 8, 50),
    AgentChatMessage.created_at <= datetime(2026, 6, 1, 9, 0)
).order_by(AgentChatMessage.created_at).all()
for m in msgs:
    print(f'[{m.created_at}] {m.role}: {m.content[:100]}')
"
```

## Prevention Checklist

- [ ] Set `syncFullHistory: false` in sidecar index.js
- [ ] Set `keepAliveIntervalMs: 15000` in sidecar index.js
- [ ] Restart sidecar after config change
- [ ] Verify disconnect interval increases beyond 50 min
- [ ] If still at 50 min: accept as known Baileys limitation, design around it
