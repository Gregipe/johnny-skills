# Voice Note Dedup Timestamp Bug

**Date:** June 9, 2026
**Root cause:** `contentDedupKey` dividing already-seconds timestamp by 1000
**Fix:** Used `msg.key.id` directly for voice note dedup instead of timestamp hash

## The Bug

In `/opt/ara/whatsapp-sidecar/index.js`, the `contentDedupKey` function:

```javascript
function contentDedupKey(text, phone, timestamp) {
  const raw = `${phone}:${text}:${Math.floor((timestamp || 0) / 1000)}`;
  return crypto.createHash('md5').update(raw).digest('hex');
}
```

For voice notes, it was called with:

```javascript
const contentKey = contentDedupKey('[voice]', ownerPhoneDigits, (msg.messageTimestamp || 0));
```

`msg.messageTimestamp` is a UNIX timestamp in **seconds** (e.g., 1781004666). `Math.floor(1781004666 / 1000)` = `1781004`. Two messages sent at timestamps 1781004666 and 1781004700 both floor to `1781004` — the same dedup key. Since `forwardedContentHashes` is an in-memory Set checked by `isAlreadyForwarded()`, the second voice note is silently skipped.

**Window size:** ~1000 seconds (16.6 minutes).

## The Fix

Changed to use the unique message ID:

```javascript
// Before:
const contentKey = contentDedupKey('[voice]', ownerPhoneDigits, (msg.messageTimestamp || 0));

// After:
const contentKey = '[voice]' + ':' + (msg.key.id || '');
```

## Debugging Trace

When a user reports "Ava didn't process my second voice note":

1. Check sidecar logs: `journalctl -u ara-whatsapp-sidecar --no-pager | grep "Voice self-chat skipped"`
2. If you see `"Voice self-chat skipped (already forwarded)"` with a different msgId than the first voice note → content hash collision
3. Also check `"Voice self-chat skipped (backlog)"` — if age > 15s, the message was received too late (WhatsApp offline delivery)
4. Check the dedup state: `cat /opt/ara/whatsapp-sidecar/dedup_state.json` — empty `{"ids":[],"hashes":[]}` means dedup was reset (normal on restart)

## Relevant Code

- `index.js` line ~73: `contentDedupKey()` function
- `index.js` line ~362: Voice note dedup call site
- `index.js` line ~88: `isAlreadyForwarded()` function  
- `index.js` line ~364: "already forwarded" log message
- `index.js` line ~358: "backlog" log message (15s ceiling)
- Line 9020 in `server.py`: Transcription truncated to 80 chars in log — always check DB for full transcript
