# Voice Pipeline: Interim Messaging & Question Detection (June 10, 2026)

## Session Summary

Greg sent a voice note at 7:25 AM IST: "Hey Eva, could you set a reminder to give me a morning briefing at 6.30am" — experienced 25 seconds of dead air, then got "Let me check the logs and offer a fix" instead of a cron being set.

## Root Causes

### 1. No interim message in voice pipeline

The voice pipeline (`whatsapp_voice_inbound()` → Whisper transcription → agent_chat call) sent zero user-visible feedback during the 25-second processing window. No "Ava is thinking..." message, no typing indicator. The user saw nothing.

**Fix added:** Interim message sent immediately before agent_chat call:
```python
try:
    if remote_jid:
        _wa.send_to_jid(remote_jid, "Ava is thinking...")
        logger.info(f"Voice: sent interim message to {remote_jid}")
except Exception:
    pass
```

**File:** `server.py` in `whatsapp_voice_inbound()`, ~line 9356

### 2. Question detection failed for emoji-prefixed transcripts

The transcript was `"🎤 hey eva, could you set a reminder..."`. The enforcer checked:
- `_has_intent = True` (keyword "set" matched) 
- `_is_question` checked `startswith(("can", "could", ...))` → False (starts with "hey", not "could")
- `"?" in msg` → False (no question mark from Whisper)
- Result: enforcer fired → wasted 16s on re-call → LLM produced "Let me check the logs" instead of calling set_cron

**Fix (3-layer question detection):**

```python
_msg_clean = _msg_lower.strip().lstrip("🎤👍💬💭️✨🌟").strip()
_question_words = ("can", "could", "would", "do", "does", "is", "are", "will", "what", "how", "should", "may")
_is_question = "?" in _msg_lower or _msg_clean.startswith(_question_words) or any(
    " " + w + " " in " " + _msg_clean[:60] + " " for w in _question_words
)
```

Layer 3 (substring match) catches `"🎤 hey eva, could you..."` — after emoji strip, `" could "` is present in the first 60 chars.

### 3. Enforcer re-call prompt was too generic

The old prompt: `"You MUST include a [TOOL_CALL:] block to actually execute. Example: update_lead..."` — the LLM responded with `"Let me check the logs and offer a fix"` (metacognition) instead of `[TOOL_CALL: set_cron(...)]`.

**Fix:** Re-call prompt now includes the specific tool list and an example matching the user's intent:

```python
"Available tools: set_cron, set_reminder, schedule_message, ..."
'Example: [TOOL_CALL: {"tool": "set_cron", "args": {"title": "Morning Briefing", "frequency": "daily", "time": "06:30"}}]'
```

## Code Locations

| Fix | File | Line |
|-----|------|------|
| Voice interim message | `server.py` → `whatsapp_voice_inbound()` | ~9356 |
| Question detection (emoji strip + substring) | `server.py` → `agent_chat()` | ~5393-5397 |
| Enforcer re-call prompt (specific tool list) | `server.py` → `agent_chat()` | ~5409-5421 |

## Latency Breakdown (Before vs After)

| Phase | Before | After |
|-------|--------|-------|
| Whisper transcription | 7s | 7s |
| First LLM call | 2s | 2s |
| Enforcer detection + re-call | 16s (fired on question) | 0s (question detected, skipped) |
| Tool execution | 2s | 2s |
| **Total** | **27s** | **11s** |
| User-visible feedback | None | `"Ava is thinking..."` at T+7s |
