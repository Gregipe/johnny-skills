# ElevenLabs STT Keyterms + Restricted API Key — Policy Violation

Date: 2026-07-10

## Symptom

Voice mode connects successfully (WebRTC, ICE, `bot-ready` received, VAD detects speech), but STT never transcribes. The server log shows:

```
ElevenLabsRealtimeSTTService#0 connection verification failed: 
  received 1008 (policy violation) invalid_request
ElevenLabsRealtimeSTTService#0 reconnection attempt 3 failed: 
  websocket reconnection failed verification
```

Then the session disconnects with `CancelFrame(idle timeout)`.

## Root Cause

The ElevenLabs API key has restricted permissions (STT+TTS only, no `user_read` or `models_read`). When `keyterms` is passed in `ElevenLabsRealtimeSTTService.Settings`, the WebSocket verification fails with 1008 (policy violation). Without `keyterms`, the WebSocket connects and transcribes normally.

The restricted key allows:
- ✅ STT (scribe_v2_realtime) — WebSocket transcription
- ✅ TTS (eleven_turbo_v2_5) — WebSocket audio generation
- ❌ `user_read` — cannot fetch user info
- ❌ `models_read` — cannot list models
- ❌ `keyterms` parameter in realtime STT — causes 1008

## Fix

Remove `keyterms` from `ElevenLabsRealtimeSTTService.Settings`:

```python
# BEFORE (causes 1008 with restricted key):
stt = ElevenLabsRealtimeSTTService(
    api_key=ELEVENLABS_API_KEY,
    settings=ElevenLabsRealtimeSTTService.Settings(
        model="scribe_v2_realtime",
        keyterms=stt_keyterms or [],  # ← REMOVE THIS
    ),
)

# AFTER (works):
stt = ElevenLabsRealtimeSTTService(
    api_key=ELEVENLABS_API_KEY,
    settings=ElevenLabsRealtimeSTTService.Settings(
        model="scribe_v2_realtime",
        # keyterms removed — restricted key doesn't support it
    ),
)
```

## The Keyterms Feature

`keyterms` biases ElevenLabs Scribe to prefer certain words during transcription. It was used to inject lead names (max 100) so Ava could recognize names like "Ramgopal" vs "Ram Gopal." Without keyterms, phonetic matching (`_phonetic_match()`) in server.py handles the fuzzy matching.

## Detection

To verify if the key has this issue:
```bash
# Will fail with 401 if key is restricted:
curl -s "https://api.elevenlabs.io/v1/user" \
  -H "xi-api-key: sk_..." 

# Will fail with 401 if key is restricted:
curl -s "https://api.elevenlabs.io/v1/models" \
  -H "xi-api-key: sk_..."
```

Both return `missing_permissions` for restricted keys. This is expected — not a bug.
