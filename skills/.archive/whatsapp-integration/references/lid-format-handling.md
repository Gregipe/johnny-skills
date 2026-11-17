# Baileys LID Format Handling

## What is LID?

LID (Local ID) is a WhatsApp protocol identifier format introduced in early 2025. It replaces the traditional phone-number JID (`919582549236@s.whatsapp.net`) with an opaque numeric identifier (`37039848317007@lid`). LIDs are per-device, non-deterministic — there's no way to derive a phone number from a LID.

## When LID Appears

- After **clearing auth** (`auth_info/` directory) and re-scanning QR
- On **first-time auth** on a new device
- **During normal operation with existing auth** (June 2026 finding) — LID format appears AFTER the `syncFullHistory: true` history sync completes. The `sock.user.id` stays in phone format (`919582549236:82@s.whatsapp.net`) but ALL `messages.upsert` events use `@lid` format for `remoteJid`. This means LID is the **default message delivery format** once Baileys transitions from AwaitingInitialSync to Online, regardless of auth state.
  - **Log signal:** After `"Timeout in AwaitingInitialSync, forcing state to Online and flushing buffer"`, all subsequent messages have `@lid` JIDs
  - **`sock.user.id` remains in phone format** — the socket user ID does NOT change to LID
  - **`remoteJid` for ALL messages uses LID** — including self-chat, DMs to contacts, and messages mistakenly identified as DMs (because `@lid != @g.us`, group messages fall through to the DM handler)
  - **`chats.update` handler was silently dropping LID chats (June 2026 fix)** — The handler had `!chat.id.endsWith('@s.whatsapp.net')` which dropped ALL `@lid` format chat updates. The events DID fire, they were just filtered out. After removing the format filter and adding LID self-chat detection, `chats.update` works for both formats. **Do NOT assert "chats.update fires zero events" — check the format filter first.**
  - **Self-chat detection via phone-digit `selfJid` is broken** — building `{digits}@s.whatsapp.net` and comparing against `{lid}@lid` never matches.
- **Not** on reconnects using existing auth (the stored credentials retain the original JID format) — THIS IS WRONG. LID format appears on reconnect after history sync completes, even with existing auth.

## Affected Code Paths

| Location | What breaks | Fix |
|----------|------------|-----|
| Sidecar `messages.upsert` group handler (line 204-205) | `sock.user.id` is `@lid`, phone extraction gives wrong number | Check `sock?.user?.phone` first; fall back to server-side @lid JID check |
| Sidecar `messages.upsert` DM handler (line 217-226) | Self-chat messages caught as `fromMe=true` with `remoteJid=@lid`. Digits-extraction builds `{phone}@s.whatsapp.net` which never matches `{lid}@lid`. Self-chat is silently dropped. | TWO approaches needed: (1) check `peer_recipient_pn` from message attrs if accessible; (2) capture owner Lid on first fromMe message for comparison |
| Sidecar `chats.update` handler (line 273-289) | Two bugs: (1) `!chat.id.endsWith('@s.whatsapp.net')` filter dropped ALL `@lid` chat updates. (2) Self-chat comparison against phone-based `selfJid` fails for `@lid`. | (1) Remove format filter — accept any non-@g.us, non-@newsletter chat.id. (2) Use `getOwnerPhone(sock)` for clean extraction and compare against BOTH `{phone}@s.whatsapp.net` AND `{lid}@lid`. |
| Server `whatsapp_inbound_webhook` (line 7517-7522) | `is_owner` check fails because LID doesn't match admin phone | Add `elif remote_jid.endswith('@lid')` fallback (broader than old `== COACHING_GROUP_JID`) |
| `_handle_owner_coach_whatsapp` | Never called for group messages | Above fix routes correctly |
| `_log_owner_reply` | May log to wrong conversation | Broad @lid fallback prevents this path |

## Debugging Checklist

When group coaching messages aren't routing:

1. **Check sidecar logs**: `"Owner reply in group"` — if absent, the message isn't reaching `messages.upsert`. Check decryption errors.
2. **Check sidecar logs**: `"Owner reply to JID ...@lid"` — if present but no DB record, the webhook handler dropped it.
3. **Check server webhook handler**: Look at `phone_clean` value. If it starts with `37` (LID range) and has 11 digits, that's LID.
4. **Verify the fix**: `elif remote_jid == COACHING_GROUP_JID` is in the webhook handler.
5. **Test**: Send another message in the group after confirming the fix is deployed.

## Server-Side Code (the fix)

```python
# In whatsapp_inbound_webhook, after is_owner check:
if owner_reply:
    if is_owner:
        _handle_owner_coach_whatsapp(...)
    elif remote_jid.endswith('@lid'):
        # LID format: can't match by phone, but @lid JID proves it's the owner
        logging.getLogger("whatsapp").info(f"LID JID fallback: routing owner reply to coaching (remote_jid={remote_jid})")
        _handle_owner_coach_whatsapp(phone_clean, message, db, message_id, remote_jid)
    else:
        lead = _find_lead_by_phone(phone_clean, db)
        if lead:
            _log_owner_reply(...)
```

**Note:** The broader `endswith('@lid')` check is preferred over the earlier `== COACHING_GROUP_JID` approach because:
1. It catches ALL LID-format JIDs, not just one known group
2. It doesn't require hardcoding a specific group JID
3. It handles group messages misidentified as DMs (@lid != @g.us), which was the actual failure mode

## Sidecar-Side (best-effort, not definitive)

```javascript
let ownerPhone = '';
if (sock?.user?.phone) {
  // Baileys v6+: phone sub-object with numeric phone
  ownerPhone = sock.user.phone.phone || '';
} else if (sock?.user?.id && !sock.user.id.includes('@lid')) {
  // Traditional JID format: phone:device@s.whatsapp.net
  ownerPhone = sock.user.id.split(':')[0].replace(/[^0-9]/g, '');
}
// If ownerPhone is still empty, pass the LID digits
// The server-side group JID fallback handles it
```

## Self-Chat LID Detection Gap

Self-chat messages sent via LID format (`@lid`) create a unique problem: the sidecar's DI handler compares `remoteJid` against a phone-number-based `selfJid` (`{digits}@s.whatsapp.net`), which never matches a LID.

**Root cause:** The `messages.upsert` and `chats.update` handlers both use:
```javascript
const ownerPhoneDigits = ownerJid.replace(/[^0-9]/g, '');
const selfJid = `${ownerPhoneDigits}@s.whatsapp.net`;
const isSelfChat = (remoteJid === selfJid);
```
When `remoteJid` is `37039848317007@lid`, building `selfJid` as `37039848317007@s.whatsapp.net` produces the wrong domain. The LID format uses `@lid` domain, not `@s.whatsapp.net`.

**Known workarounds:**
1. **Capture owner LID on connect** — when `sock.ev.on('connection.update')` fires with `connection === 'open'`, check if `sock.user.id` ends with `@lid`. If so, store it as `ownerLid` and use it as an additional comparison in the self-chat check:
   ```javascript
   const isSelfChat = (remoteJid === selfJid || remoteJid === ownerLid);
   ```
2. **Prefer coaching group** — group messages are reliably routed and don't rely on JID matching for self-chat detection.

**Full details:** `references/self-chat-lid-detection.md`

## Prevention

- **Never clear auth unless necessary.** LID format appears on every fresh auth. If you can reconnect without clearing auth, the JID format stays stable.
- **Log `sock.user.id` on connect** to detect LID format early: `logger.info('Connected as: ' + sock?.user?.id)`.
- **The server-side group JID fallback is the definitive fix.** Sidecar-level fixes are best-effort.
