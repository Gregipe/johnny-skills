# Coaching UX: Response Format + Typing Indicator + Reaction Timing

## Response Format Convention (Updated June 2026)

Ava's coaching replies use this exact format:

```
✨ *Ava :*

[reply text here]
```

### Format Details
- **Icon:** ✨ (Unicode `\u2728`, "sparkles") — Greg chose this over the previous ✦ (`\u2726`, black star). Referred to as "the cluster of stars" icon.
- **Bold name:** `*Ava :*` with a colon, spaced from the icon by a single space
- **Blank line** between the name line and the reply body
- **Stored in server.py** as: `formatted = "\\u2728 *Ava :*\\n\\n" + ava_reply`

### Previous Format
Before June 2026, the format was `"Ava: " + ava_reply` (no icon, no bold).

### Editing the Unicode Escape
**CAUTION:** The Unicode escape `\\u2728` is stored as a literal double-escaped string in Python source. The `patch` tool cannot match it — see `references/patch-tool-unicode-edge-case.md` for the Python string replacement workaround.

## User Expectation

When Greg sends a message to the coaching group or self-chat, the expectations are:

1. **👍 Reaction** — Fires immediately (within 1s) — confirms "Ava received your message"
2. **Typing indicator** — Starts within 1-2 seconds of the reaction — signals "Ava is generating a response"
3. **Actual response** — Arrives 3-4 seconds after sending — the formatted response

**Current state (June 2026):** The 👍 reaction fires but the typing indicator is still missing. The response arrives after 3-4 seconds of radio silence, which feels abrupt.

## Where the Typing Indicator is Fired

In `server.py`, `_handle_owner_coach_whatsapp()`:

```python
# Fire typing + reaction in parallel immediately (non-blocking)
if remote_jid:
    import threading as _t
    def _fire_typing():
        try:
            import requests as _r
            _r.post("http://localhost:8767/api/typing", json={
                "jid": remote_jid, "action": "composing"
            }, timeout=1)
        except Exception:
            pass
    if message_id:
        def _fire_reaction():
            try:
                import requests as _r
                _r.post("http://localhost:8767/api/react", json={
                    "jid": remote_jid, "message_id": message_id, "emoji": "👍"
                }, timeout=3)
            except Exception:
                pass
        _t.Thread(target=_fire_reaction, daemon=True).start()
    _t.Thread(target=_fire_typing, daemon=True).start()
```

## Why Typing Might Not Show

### 1. Timing Race Condition
The typing fires at the start, but the function takes 3-4s (DB writes + LLM call + send). Baileys typing indicators last ~6-10s, so timing alone shouldn't be the issue, but the indicator may not show at all in some cases.

### 2. Sidecar `/api/typing` Endpoint
```javascript
app.post('/api/typing', async (req, res) => {
  const { jid, action } = req.body;
  if (!jid || !action) return res.status(400).json({ ok: false, error: 'jid and action required' });
  try {
    await sock.sendPresenceUpdate(action, jid);
    res.json({ ok: true });
  } catch (e) {
    res.json({ ok: false, error: e.message });
  }
});
```

### 3. Baileys Presence Throttling
Baileys may throttle `sendPresenceUpdate('composing', jid)` if too many are sent per JID (rate limit ~1 per 5s per JID), or if the connection is in "syncing" state.

### 4. Group JID Limitation (Likely Root Cause)
`sendPresenceUpdate()` is primarily designed for 1:1 chats. For group JIDs (`@g.us` / `@lid`), Baileys may silently drop composing signals. This is a Baileys/WhatsApp limitation — presence indicators in groups only show for the specific participant, not as a group-wide typing indicator.

## Fixes Implemented

### Keepalive Thread (June 2026)
Fires composing every 2 seconds during LLM processing via a daemon thread, then stops it right before sending:

```python
_typing_stop = threading.Event()
def _typing_keepalive():
    while not _typing_stop.is_set():
        try:
            requests.post("http://localhost:8767/api/typing", json={
                "jid": remote_jid, "action": "composing"
            }, timeout=1)
        except Exception:
            pass
        _typing_stop.wait(2.0)
_t.Thread(target=_typing_keepalive, daemon=True).start()

# ... LLM call ...

_typing_stop.set()
requests.post("http://localhost:8767/api/typing", json={
    "jid": reply_jid, "action": "composing"
}, timeout=1)
wa.send_to_jid(reply_jid, formatted)
```

Still unconfirmed whether this works for group chats.

## If Keepalive Still Doesn't Work

- Check `/api/typing` endpoint receives requests (add logging to sidecar typing handler)
- Try sending composing to individual participant JIDs in the group (doesn't scale)
- Consider that WhatsApp groups simply don't support external typing indicators from bots
- Alternative UX: send an interim message ("One moment...") instead of typing indicator
