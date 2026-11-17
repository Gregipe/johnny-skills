# Voice Pipeline Edge Cases — Interim Messaging, Error Recovery, Dedup (June 10, 2026)

## What Changed

Complete overhaul of the voice-inbound endpoint (`POST /api/whatsapp/voice-inbound`) to eliminate silent failures and dead air.

## The 7 Edge Cases Fixed

### 1. JID Fallback — Empty remote_jid

**Problem:** If the sidecar didn't pass `remote_jid`, the voice pipeline had no way to send interim/response messages back to the user. Dead air.

**Fix:** Default to `COACHING_GROUP_JID` if `remote_jid` is empty:
```python
if not remote_jid:
    remote_jid = COACHING_GROUP_JID
```

### 2. Import Order — _wa Used Before Import

**Problem:** The interim message block was inserted BEFORE `from whatsapp_sidecar_client import wa as _wa`. The interim message called `_wa.send_to_jid()` which raised NameError, caught silently by `except Exception: pass`. User saw nothing.

**Fix:** Move the import above the interim message block:
```python
from whatsapp_sidecar_client import wa as _wa

# Interim message — _wa is now defined
try:
    if remote_jid:
        _wa.send_to_jid(remote_jid, "⏳ Processing your voice note...")
except Exception:
    pass
```

### 3. Interim Timing — Send BEFORE Slow Operations

**Problem:** Interim message was sent AFTER transcription (5-7s delay). The user experienced dead air during the wait.

**Fix:** Send the interim message BEFORE audio decode and transcription — immediately after import and dedup check:
```python
# Interim message sent BEFORE potentially slow operations
_wa.send_to_jid(remote_jid, "⏳ Processing your voice note...")
```

### 4. Empty Transcript — Silent Return

**Problem:** If Whisper returned empty transcript, the handler returned early with `{"status": "error", "reason": "Empty transcript"}` — no message sent to user.

**Fix:** Send an error message before returning:
```python
if not transcript:
    try:
        _wa.send_to_jid(remote_jid, "Sorry, I could not understand the audio.")
    except Exception:
        pass
    return {"status": "error", "reason": "Empty transcript"}
```

### 5. Agent Chat 500 — Silent Error

**Problem:** If agent_chat returned HTTP 500, the handler logged the error but sent nothing to the user.

**Fix:** Send error fallback message:
```python
else:
    logger.error(f"Voice: agent chat returned {resp.status_code}")
    try:
        _wa.send_to_jid(remote_jid, "Sorry, I ran into an error. Try text?")
    except Exception:
        pass
```

### 6. Top-Level Exception — Silent Crash

**Problem:** If any uncaught exception occurred (audio decode, DB, network), the outer try/except logged it but sent nothing.

**Fix:** Add error message to outer exception handler:
```python
except Exception as e:
    logger.error(f"Voice inbound error: {e}")
    try:
        _wa.send_to_jid(remote_jid, "Sorry, I ran into an error.")
    except Exception:
        pass
```

### 7. Dedup — Voice Notes Not Registered

**Problem:** Voice notes were checked against `_coach_processed_ids` (the in-memory dedup dict) but never WRITTEN to it. On first message, the check passed (not in dict), then was never recorded. Subsequent duplicates of the same voice note wouldn't be caught.

**Fix:** Write to dedup dict after successful processing:
```python
try:
    if message_id:
        _coach_processed_ids[message_id] = time.time()
        if time.time() - _DEDUP_LAST_SAVE > 5:
            _save_dedup()
            _DEDUP_LAST_SAVE = time.time()
except Exception:
    pass
```

## Key Lesson: Every Exit Point Needs a User-Facing Message

**Rule:** Every return/exit in the voice pipeline must send SOMETHING to the user via WhatsApp before returning. The only exception is the dedup exit (duplicate → drop silently, no message needed).

**Path audit checklist:**
- [x] No audio data → silent (can't send — no JID yet)
- [x] Dedup hit → silent drop (correct — user already saw the response)
- [x] Empty transcript → "Sorry, couldn't understand"
- [x] agent_chat error → "Sorry, ran into an error"
- [x] Top-level exception → "Sorry, ran into an error"
- [x] Success → response text sent

## Interim Message Text

Use `"⏳ Processing your voice note..."` (not "Ava is thinking") — the hourglass emoji signals async processing, while "Ava is thinking" sounds like she hasn't started yet.

## Related

- `references/enforcer-improvements-june2026.md` — enforcer question detection fixes (voice notes arrive with 🎤 prefix)
- `ara-agent-tools` SKILL.md → Pre-Execution Enforcer section (data-tool-only check)
