# Scribe v2 STT Integration (June 25, 2026)

## Overview
Replaced faster-whisper small.en with ElevenLabs Scribe v2 (#1 ranked STT model on Artificial Analysis leaderboard) for voice note transcription. Scribe v2 is used when `ELEVENLABS_API_KEY` is set in `/opt/ara/.env`; falls back to Whisper otherwise.

## Integration File
`/opt/ara/scribe_stt.py` — standalone module with `transcribe_scribe()` and `is_available()`.

## Key Decisions

### Multipart form upload (not JSON)
The ElevenLabs STT API uses multipart form, not JSON. First attempt with base64-encoded JSON body returned 422. Correct pattern:

```python
with open(audio_path, "rb") as fh:
    files = {"file": (os.path.basename(audio_path), fh, "audio/ogg")}
    data = {"model_id": "scribe_v2", "diarize": "true", "tag_audio_events": "false"}
    r = requests.post("https://api.elevenlabs.io/v1/speech-to-text",
        headers={"xi-api-key": key}, files=files, data=data, timeout=120)
```

### Diarization enabled by default
Scribe v2 supports speaker diarization — who said what. Enabled by default. Words are grouped into segments with speaker labels. When available, the transcript is formatted as `[SPEAKER_0]: text\n[SPEAKER_1]: text`. This is critical for the eval agent's owner routing (`agent` vs `ava_send`).

### cost
- Scribe v2 batch: $0.22/hour = ₹18/hour
- 15-minute meeting: ₹4.50
- 50 meetings/month: ₹225

## API Key
Set `ELEVENLABS_API_KEY` in `/opt/ara/.env`. The `scribe_stt.py` module loads it from the .env file (not environment variables).

## Fallback
When Scribe v2 is unavailable (no key, API error), the voice pipeline falls back to faster-whisper small.en. The `is_available()` function gates this.

## Pitfalls

### .env key format
The key must be stored as `ELEVENLABS_API_KEY=sk_...` with the `ELEVENLABS_API_KEY=` prefix. Appending just the raw key to .env (without the variable name) causes `is_available()` to return False.

### API endpoint
The endpoint is `POST /v1/speech-to-text` — NOT `/v1/speech-to-text/convert` or any subpath. A 422 error typically means wrong request format (multipart vs JSON).

### Model ID
Use `"scribe_v2"` for batch transcription. There's also `"scribe_v2_realtime"` for live transcription (not used in Phase 1).
