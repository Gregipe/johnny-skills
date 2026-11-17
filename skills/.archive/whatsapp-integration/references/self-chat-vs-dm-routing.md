# Self-Chat vs DM Routing: Preventing Ava From Replying to Personal Contacts

## The Bug

Owner sends a personal WhatsApp message to a friend or family member. Ava replies to that person with a coaching response prefixed "Ava: ".

## Root Cause Chain

1. **`emitOwnEvents: true`** in the sidecar (`index.js`) makes Baileys emit events for every message the owner sends — including messages to non-lead personal contacts.

2. **Three independent leak paths in the sidecar**, each forwarding owner messages to ARA:

   **Path A — `messages.upsert` DM handler:** No self-chat guard in the `isFromMe` DM handler. The old code blindly forwarded ALL owner DMs to ARA:
   ```javascript
   // OLD: forwards EVERY owner DM
   } else if (isFromMe) {
       const ownerPhone = ownerJid.split(':')[0].replace(/[^0-9]/g, '');
       sendToARA(ownerPhone, 'Owner', text, true, msg.key.id, remoteJid);
   }
   ```

   **Path B — `chats.update` handler:** This handler was designed as a self-chat fallback (since `messages.upsert` doesn't fire for all self-chat scenarios), but it only checked `isFromMe` — never verified the chat was actually self-chat. Every `fromMe` chat update was forwarded to ARA:
   ```javascript
   // OLD: checks isFromMe but NOT self-chat — forwards all outgoing DMs
   const isFromMe = lastMsg.key?.fromMe || false;
   if (!isFromMe) continue;
   sendToARA(phone, 'Owner', text, true, lastMsg.key?.id || '', chat.id);
   ```

   **Path C — Group handler:** The `isGroup` handler forwarded owner replies in ANY group, not just the known coaching group:
   ```javascript
   // OLD: forwards owner replies in ALL groups
   if (isFromMe) {
       const ownerPhone = ownerJid.split(':')[0].replace(/[^0-9]/g, '');
       sendToARA(ownerPhone, 'Owner', text, true, msg.key.id, remoteJid);
   }
   ```

3. **ARA webhook routed all `owner_reply=true` + `is_owner=true` to coaching** without checking who the recipient was:

   ```python
   # OLD: routes every owner message to coaching regardless of recipient
   if owner_reply:
       if is_owner:
           _handle_owner_coach_whatsapp(phone_clean, message, db, message_id, remote_jid)
   ```

4. **`_handle_owner_coach_whatsapp` sends Ava's reply to `remote_jid`** — which is the personal contact's JID:

   ```python
   reply_jid = remote_jid if remote_jid else COACHING_GROUP_JID
   wa.send_to_jid(reply_jid, "Ava: " + ava_reply)
   ```

## The Fix (Two-Layer + Three Paths)

### Layer 1 — Sidecar: Three Independent Guards

**Guard A — `messages.upsert` DM handler (self-chat check with digits-extraction):**
```javascript
} else if (isFromMe) {
    // Digits-extraction: handle "919582549236.0:4@s.whatsapp.net" -> "919582549236" -> selfJid
    const ownerJid = sock?.user?.id || '';
    const ownerPhoneDigits = ownerJid.replace(/[^0-9]/g, '');
    const selfJid = `${ownerPhoneDigits}@s.whatsapp.net`;
    const isSelfChat = (remoteJid === selfJid);
    if (!isSelfChat) {
      logger.info(`Owner DM to ${remoteJid}: skipped (not self-chat)`);
      continue;
    }
    logger.info(`Self-chat DM: "${text.substring(0, 60)}..."`);
    sendToARA(ownerPhoneDigits, 'Owner', text, true, msg.key.id, remoteJid);
}
```

**Guard B — `chats.update` handler (same digits-extraction approach):**
```javascript
const isFromMe = lastMsg.key?.fromMe || false;
if (!isFromMe) continue;

// Same digits-extraction approach as messages.upsert
const ownerJid2 = sock?.user?.id || '';
const ownerPhoneDigits2 = ownerJid2.replace(/[^0-9]/g, '');
const selfJid2 = `${ownerPhoneDigits2}@s.whatsapp.net`;
const isSelfChat2 = (chat.id === selfJid2);
if (!isSelfChat2) {
  logger.info(`Chats.update for ${chat.id}: skipped (not self-chat)`);
  continue;
}
sendToARA(phone, 'Owner', text, true, lastMsg.key?.id || '', chat.id);
```

**Guard C — Group handler (coaching group JID filter):**
```javascript
if (isGroup) {
    if (isFromMe) {
      if (remoteJid !== COACHING_GROUP_JID) {
        logger.info(`Owner reply in non-coaching group ${remoteJid}: skipping`);
        continue;
      }
      // ... forward to coaching
    }
}
```

**Self-chat matching logic (digits-extraction approach for guards A and B):**
- `sock.user.id` format: `"919582549236@s.whatsapp.net"` or `"919582549236.0:4@s.whatsapp.net"` or LID format `"37039848317007@lid"`
- Extract only digits: `ownerJid.replace(/[^0-9]/g, '')` → `919582549236`
- Build self JID: `${phoneDigits}@s.whatsapp.net`
- Compare: `remoteJid === selfJid`
- **Does NOT handle LID format `@lid`** — when `remoteJid` is `37039848317007@lid`, building `{digits}@s.whatsapp.net` produces `37039848317007@s.whatsapp.net` which doesn't match `37039848317007@lid`. See `references/self-chat-lid-detection.md` for the known gap and potential fix.

**What gets forwarded:** Only self-chat DMs and messages in the specific coaching group. Owner replies to leads in DM are NOT currently forwarded by the sidecar. Non-coaching group messages are also skipped.

### Layer 2 — Server: Safe-Coaching-Target Validation + Logger Fix

In `server.py`, the `whatsapp_inbound_webhook` now verifies `remote_jid` against the specific coaching group JID (not any `@g.us`) before routing to coaching, and uses a properly-scoped logger:

```python
_wal = logging.getLogger("whatsapp")  # At function top — avoids NameError in except block

if owner_reply:
    if is_owner:
        owner_self_jid = f"{phone_clean}@s.whatsapp.net"
        is_safe_coaching = (remote_jid == WA_COACHING_GROUP_JID) or remote_jid == owner_self_jid
        if is_safe_coaching:
            _handle_owner_coach_whatsapp(phone_clean, message, db, message_id, remote_jid)
        else:
            if remote_jid.endswith('@s.whatsapp.net'):
                rp = remote_jid.replace('@s.whatsapp.net', '')
                rp_clean = "".join(c for c in rp if c.isdigit())
                if rp_clean:
                    lead = _find_lead_by_phone(rp_clean, db)
                    if lead:
                        _log_owner_reply(phone, message, db)
                        _wal.info(f"Owner DM to lead {lead.name}: logged reply")
                    else:
                        _wal.info(f"Dropped owner DM to non-lead JID {remote_jid}")
```

**Key changes from old code:**
1. `WA_COACHING_GROUP_JID` replaces `@g.us` — only the specific coaching group is a safe target
2. `_wal` at function top replaces bare `logger` / per-branch `_walog` — `logger` was undefined in the except block, causing a `NameError` crash that killed the server

## Verification

To verify the fix is working:

1. **Send a WhatsApp message to a personal contact** — check sidecar logs (`/tmp/sidecar.log`). You should see:
   ```
   Owner DM to <contact-jid>: skipped (not self-chat)
   ```
   No `sendToARA` call for that message.

2. **Message yourself (self-chat)** — should show:
   ```
   Self-chat DM: "your message..."
   ```
   And Ava's coaching reply should appear in your self-chat.

3. **Message in a non-coaching group** — sidecar log should show:
   ```
   Owner reply in non-coaching group <group-jid>: skipping
   ```

4. **Message in the coaching group** — should work as before, Ava responds with "Ava: " prefix.

5. **Check server logs for `_wal` (no crash)**: No `NameError: name 'logger' is not defined` in the ARA logs.

## Side Effects

- `emitOwnEvents: true` is still needed for self-chat detection via `chats.update` and group message detection. All three guards only filter — they don't disable the event.
- Owner replying directly to a lead's DM (not through coaching) will NOT trigger an Ava auto-response currently. The sidecar skips all non-self-chat owner DMs. If this feature is needed, a separate pathway must be added.
- Non-coaching groups are now completely ignored — owner replies in family/work groups are never forwarded to ARA.
- The `_wal` logger at function top is a structural fix — any future exceptions in the webhook will be properly logged instead of crashing the server.
