# Group-Based Coaching (Self-Chat Alternative)

## The Problem

WhatsApp multi-device protocol **does not emit self-chat messages** through Baileys — neither via `messages.upsert` (any type: notify/append) nor reliably via `chats.update` (the `lastMessage` field is often absent from the update payload). This means the owner cannot coach Ava by replying to messages in the "Note to Self" (self-chat) conversation.

**Root cause**: Self-chat messages are stored locally on the phone — they never hit WhatsApp's servers for delivery, so no WebSocket push event is generated for secondary devices.

## The Fix: WhatsApp Group

Group messages DO trigger `messages.upsert` with type `"notify"` — WhatsApp groups require server-side message routing (even single-member groups). Create a private group and use it as the coaching channel.

### Architecture

```
Owner replies in group ─→ messages.upsert(notify) ─→ Sidecar → ARA webhook
                               ↑
ARA sends coaching responses ──┘ (via /send-jid to group JID)

Detection:
  msg.key.fromMe === true (same WhatsApp account)
  + msg.key.id NOT in sentMsgIds (not a bot-sent message)
  + remoteJid endsWith('@g.us') (group)
  → Owner replying in coaching group → route to coaching
```

### Setup Steps

1. **Create a WhatsApp group** via the sidecar's `/create-group` endpoint:
```bash
curl -X POST http://localhost:8767/create-group \
  -H "Content-Type: application/json" \
  -d '{"title":"ARA Coaching","participants":["<owner_phone>@s.whatsapp.net"]}'
```

2. **Store the group JID** (e.g., `120363429248150974@g.us`) as a server constant:
```python
COACHING_GROUP_JID = "120363429248150974@g.us"
```

3. **Update server coaching functions** to use `send_to_jid()` instead of `send_message_sync()`:
```python
# Before (self-chat — doesn't work):
wa.send_message_sync(admin.phone, "Ava: " + message)

# After (group — works):
wa.send_to_jid(COACHING_GROUP_JID, "Ava: " + message)
```

4. **Update sidecar's `messages.upsert` handler** to process group messages from the owner:
```javascript
// Don't skip groups anymore — detect owner coaching replies:
if (remoteJid.endsWith('@g.us')) {
  if (isFromMe) {
    // Owner replied in coaching group
    const ownerJid = sock?.user?.id || '';
    const ownerPhone = ownerJid.split(':')[0].replace(/[^0-9]/g, '') || phone;
    sendToARA(ownerPhone, 'Owner', text, true, msg.key.id, remoteJid);
  }
  // Non-fromMe group messages are skipped (Ava handles leads via DMs)
}
```

### Owner Phone Extraction for Groups

For group messages from the owner, `msg.key.participant` gives a LID (e.g., `37039848317007:77@lid`) — NOT the phone number. Use `sock.user.id` instead:

```javascript
const ownerJid = sock?.user?.id || '';
const ownerPhone = ownerJid.split(':')[0].replace(/[^0-9]/g, '') || phone;
```

`sock.user.id` contains the connected account's JID in the format `<phone>:<device_id>@s.whatsapp.net`.

### Sidecar Extensions Needed

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/send-jid` | POST | Send to any JID (group or phone) — `{"jid": "...", "text": "..."}` |
| `/create-group` | POST | Create WhatsApp group — `{"title": "...", "participants": ["jid1", ...]}` |

The `/send` endpoint also accepts an optional `jid` parameter alongside `phone`.

### Python Client Extensions

```python
class BaileysWA:
    def send_to_jid(self, jid, text):
        """Send to a specific JID (group, etc.)."""
        result = _req("POST", "/send-jid", {"jid": jid, "text": text}, timeout=15)
        if result.get("ok"):
            return {"status": "sent", "msg_id": result.get("msgId")}
        return {"error": result.get("error", "Unknown send error")}
```

## Server Routing Fix (Critical)

The `owner_reply` webhook handler had a dangerous routing bug: `_find_lead_by_phone()` was checked **before** `is_owner`. Since the owner's own phone number exists in the `leads` table (Gregory Ipe is a lead in the Hunar DB), `owner_reply: true` messages were routed to `_log_owner_reply()` instead of `_handle_owner_coach_whatsapp()`. The coaching function never ran — Ava never saw the message.

**Fix**: Check `is_owner` first for `owner_reply` messages:

```python
if owner_reply:
    if is_owner:
        # Coach: owner replied in group or self-chat
        _handle_owner_coach_whatsapp(phone_clean, message, db, message_id, remote_jid)
    else:
        lead = _find_lead_by_phone(phone_clean, db)
        if lead:
            _log_owner_reply(phone, message, db)
```

### LID Format Fallback (After Fresh Auth)

After clearing auth and re-scanning QR, Baileys may return `sock.user.id` in LID format (e.g., `37039848317007@lid`). The sidecar extracts a bogus phone (`37039848317007`) from this, which doesn't match the owner's real number in the `users` table. The `is_owner` check fails, and the message is silently dropped.

**Fix:** Add a fallback that checks `remote_jid` against `COACHING_GROUP_JID`. If the message came from the coaching group, route it to coaching regardless of the phone:

```python
if owner_reply:
    if is_owner:
        _handle_owner_coach_whatsapp(phone_clean, message, db, message_id, remote_jid)
    elif remote_jid == COACHING_GROUP_JID:
        # LID format mis-match: message is from the coaching group, so it's the owner
        logger.info(f"LID fallback: routing group {remote_jid} message as owner coaching")
        _handle_owner_coach_whatsapp(phone_clean, message, db, message_id, remote_jid)
    else:
        lead = _find_lead_by_phone(phone_clean, db)
        if lead:
            _log_owner_reply(phone, message, db)
```

**Why this works:** Only the owner's message appear as `fromMe: true` in the group. If a group message has `owner_reply=True`, it can only be from the owner. The group JID is the reliable identifier, not the phone number.

**Detection:** Check sidecar logs for `"Owner reply in group ..."` — if that appears but no `AgentChatMessage` is created in the DB, the LID phone mismatch is the likely cause. Check the webhook handler's `phone_clean` value — if it's an 11-digit number starting with `37...` like `37039848317007`, that confirms LID format.

### Origin-Based Reply Routing (Dual-Path Support)

The `_handle_owner_coach_whatsapp` function should send responses back to the **origin JID** rather than always using `COACHING_GROUP_JID`. This enables both group and self-chat paths to work simultaneously:

```python
# Send Ava's response back to the origin (self-chat or group)
reply_jid = remote_jid if remote_jid else COACHING_GROUP_JID
from whatsapp_sidecar_client import wa
wa.send_to_jid(reply_jid, "Ava: " + ava_reply)
```

**How it works:**
- If the owner replied in the **group** → `remote_jid` is the group JID → reply goes back to the group ✅
- If the owner replied in **self-chat** → `remote_jid` is the self-chat JID → reply goes back to self-chat ✅
- If triggered by a **cron/alert** → `remote_jid` is empty → falls back to `COACHING_GROUP_JID` (default: self-chat JID)

**Important:** The `COACHING_GROUP_JID` constant still serves as the default for cron/alert messages. Set it to self-chat (`919582549236@s.whatsapp.net`) for personal alerts, or to the group JID for team visibility. The choice only affects automated messages — coaching replies always go to the origin.

### Pitfall: Server restart after code change

When you modify server.py (or any ARA server file), the running server process is **not automatically restarted**. The old process continues serving requests with the old code. This means:
- You patch `wa.send_to_jid(COACHING_GROUP_JID, ...)` to use `reply_jid = remote_jid if remote_jid else COACHING_GROUP_JID`
- But the running server still sends to `COACHING_GROUP_JID`
- Greg replies in the group → server processes it → sends response... to the old target ❌

**Always verify:** Check the PID start time vs file modification time:
```bash
echo "PID start: $(ps -p $(pgrep -f 'server.py$') -o lstart= 2>/dev/null)"
echo "File mtime: $(ls -l /Users/greg/ara/server.py | awk '{print $6, $7, $8}')"
```

If PID started BEFORE file mtime, you need to restart. See `systematic-change-workflow` for the full protocol.

When `syncFullHistory: true` and auth was cleared, Baileys tries to decrypt old group messages with missing session keys. This produces a burst of non-fatal errors:

```
SessionError: No session record
PreKeyError: Invalid PreKey ID
```

And Baileys sends "sent retry receipt" messages attempting to negotiate new keys. During this ~10s window, new group messages may arrive via `messages.upsert` but will be delayed while the retry negotiation completes.

**What happens:** The `messages.upsert` handler still fires for the new message. If the decryption succeeds (after retry), the message is processed normally. If it fails, Baileys continues retrying. Eventually session keys are established and everything works.

**Impact on group coaching:** If the owner sends a coaching message during the retry window, the message WILL be detected by the handler (the `msg.message` field check at line 179 may return an empty message object — skip these). The retry negotiation resolves within ~10s, and subsequent messages work fine.

**Verification:** Check sidecar logs for the retry receipt count. If you see 2-3 retries followed by the `"Owner reply in group"` log, the message was received successfully after the retry completed.

## Comparison with Self-Chat Approaches

| Approach | Reliability | Latency | Setup Complexity |
|----------|-------------|---------|-----------------|
| `messages.upsert` + emitOwnEvents | ❌ Never fires for self-chat | N/A | None |
| `chats.update` with lastMessage | ⚠️ `lastMessage` often absent | 1-5s if it works | Moderate |
| **WhatsApp Group** | ✅ Always fires `notify` events | Near-instant | Low (create group) |
| Playwright/Web poller | ✅ Works but fragile | 5-30s | High |

## Testing Checklist

1. [ ] Create group via `/create-group` — verify `groupId` returned
2. [ ] Send test via `/send-jid` to group — verify it appears on phone
3. [ ] Reply in group on phone — check sidecar logs for `"Owner reply in group"`
4. [ ] Verify server created `AgentChatMessage` with `tenant_id` set
5. [ ] Verify server sent response back via `send_to_jid()` to group
6. [ ] Verify sidecar log shows `"WhatsApp sent to <group_id>"`
