# Self-Chat Detection with LID Format JIDs

## The Problem

Baileys uses LID format JIDs (`@lid`) for message delivery after `syncFullHistory: true` completes and the connection transitions from AwaitingInitialSync to Online. This breaks self-chat detection because:

- `sock.user.id` stays in phone format: `919582549236:82@s.whatsapp.net`
- All `messages.upsert` events use `@lid` for `remoteJid`
- `chats.update` fires ZERO events when LID is active

The digits-extraction approach (`ownerJid.replace(/[^0-9]/g, '')` → `919582549236`, building `selfJid = 919582549236@s.whatsapp.net`) produces a phone-based JID that never matches the LID format `remoteJid` (`37039848317007@lid`).

## Evidence from June 2026 Debug Session

### LID Transition Detection
The transition to LID format is marked by this log line:
```
Timeout in AwaitingInitialSync, forcing state to Online and flushing buffer
```
Immediately after this, ALL `messages.upsert` events use `@lid` JIDs.

### Key Findings
1. LID format DOES NOT require fresh auth — it happens during NORMAL operation after history sync timeout
2. `sock.user.id` stays in phone format — it does NOT switch to LID
3. `chats.update` logs ZERO entries during LID mode — the handler is completely inactive
4. Both self-chat AND DMs to contacts use LID format for `remoteJid`
5. For self-chat, `from === recipient` in msgAttrs (same LID); for DMs, they differ
6. `peer_recipient_pn` in msgAttrs contains the actual phone number for self-chat

### The Effect
```javascript
// sock.user.id = "919582549236:82@s.whatsapp.net"
// ownerPhoneDigits = "919582549236"
// Built selfJid = "919582549236@s.whatsapp.net"
// Actual remoteJid for self-chat = "37039848317007@lid"
// Comparison: "919582549236@s.whatsapp.net" !== "37039848317007@lid"
// Result: skipped as "not self-chat"
```

## Symptoms
- Self-chat messages are silently dropped at the sidecar level
- Logs show: `Owner DM to 37039848317007@lid: skipped (not self-chat)`
- No `Self-chat DM` log appears
- No response from Ava
- The `chats.update` handler does NOT fire (no "Chats.update" logs at all)

## Debugging Commands
```bash
# Check if LID is active in your session
grep "DEBUG fromMe DM:" /tmp/sidecar.log | head -3
# Look for remoteJid ending in @lid — if present, LID is active

# Check for the transition to online
grep "Timeout in AwaitingInitialSync" /tmp/sidecar.log

# Check if self-chat in LID format is being caught
grep "skipped (not self-chat)" /tmp/sidecar.log | tail -5

# Check ARA server logs for webhook errors
grep "whatsapp_inbound_webhook.*error" /tmp/ara_errors.log 2>/dev/null || echo "No errors"
```

## Why chats.update Doesn't Seem to Fire in LID Mode

When LID format JIDs are active, ALL message delivery happens through `messages.upsert`. The `chats.update` events STILL fire — they were being silently dropped by the format filter `!chat.id.endsWith('@s.whatsapp.net')` at line ~245 of the original sidecar code. After removing this filter, `chats.update` catches LID-format self-chat messages normally.

**Root cause of the silence (corrected June 2026):** The original `chats.update` handler filtered out ALL JIDs that didn't end with `@s.whatsapp.net`. Since LID mode uses `@lid` JIDs, every single `chats.update` event was silently dropped at the filter line — never reached the self-chat detection logic. The fix is to accept both formats.

**Diagnostic test:** Add a log statement at the start of the `chats.update` handler (before any filter) to confirm events are received:
```javascript
sock.ev.on('chats.update', (chats) => {
  for (const chat of chats) {
    console.log(`Chats.update received: ${chat.id}`);
    // ... rest of handler
  }
});
```

## What Does NOT Work

### Phone-digit extraction comparison
```javascript
const ownerPhoneDigits = ownerJid.replace(/[^0-9]/g, '');
const selfJid = `${ownerPhoneDigits}@s.whatsapp.net`;
const isSelfChat = (remoteJid === selfJid);  // FAILS: @lid !== @s.whatsapp.net
```

### split(':') approach
```javascript
const ownerJidBase = ownerJid.split(':')[0];  // "919582549236.0" — also wrong
```

## THE FIX (Implemented June 2026) — Use `sock.user.lid`

Baileys exposes the owner's LID via `sock.user.lid`. During the June 2026 debugging session, we discovered:

```javascript
sock.user.id  // "919582549236:82@s.whatsapp.net" (phone format, always stays this)
sock.user.lid // "37039848317007:82@lid" (LID format, always stays this)
```

**Fix**: Check BOTH the phone-based JID AND the LID-based JID for self-chat detection, with a fallback through `authState.creds.me.lid`:

```javascript
const ownerPhoneDigits = getOwnerPhone(sock);
const phoneSelfJid = `${ownerPhoneDigits}@s.whatsapp.net`;

// Build all possible self-chat JIDs
const possibleSelfJids = [phoneSelfJid];

// Try sock.user.lid (populated after connection.open)
const ownerLid = sock?.user?.lid || '';
const lidBase = ownerLid.split(':')[0];
if (lidBase) possibleSelfJids.push(`${lidBase}@lid`);

// Fallback: authState.creds.me.lid (available earlier than sock.user.lid)
if (!lidBase) {
  const me = sock?.authState?.creds?.me;
  if (me?.lid) {
    const credsLidBase = me.lid.split(':')[0];
    if (credsLidBase) possibleSelfJids.push(`${credsLidBase}@lid`);
  }
}

const isSelfChat = possibleSelfJids.includes(remoteJid);
```

**Key insight**: `sock.user.lid` is available at ALL times — it's not just a connection-time value. The LID's device suffix (`:82`) must be stripped by splitting on `:` and taking the first part. The resulting `lidBase` matches `remoteJid` (which is the LID without device suffix) exactly for self-chat.

This fix works for BOTH `messages.upsert` and `chats.update` handlers.

### DO NOT use split(':')[0] on sock.user.id

```javascript
const ownerJidBase = ownerJid.split(':')[0];
// ownerJid = "919582549236:82@s.whatsapp.net"
// ownerJidBase = "919582549236" — OK this actually works for phone format
// But remoteJid for self-chat = "37039848317007@lid" — never matches
```

The split on `id` isn't harmful (it gives just the phone number), but it doesn't help with LID matching because `sock.user.id` is always in phone format.

### Verification

After implementing:
1. Send yourself a message on WhatsApp
2. Check sidecar logs for `Self-chat DM:` — if you see it, self-chat is being detected
3. If you still see `Owner DM to ...@lid: skipped (not self-chat)`, the fix isn't deployed yet

## Defense-in-Depth
For now, self-chat via LID format is a KNOWN GAP. Mitigations:
1. Prefer the coaching group for reliable interaction — group messages work
2. Once LID format is the stable ID format for the session, it stays consistent until reconnection
