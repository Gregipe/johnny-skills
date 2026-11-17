# Dictation / Speech-to-Text Implementation

## Current: MediaRecorder → Server → Scribe v2 (June 2026)

Replaced the browser-native Web Speech API with a three-tier pipeline: browser `MediaRecorder` captures audio → uploads to server endpoint → ElevenLabs Scribe v2 transcribes.

### Architecture

```
Browser: MediaRecorder → audio/webm blob
    ↓ POST /api/induction/{tenant_id}/voice-transcribe
Server: temp file → transcribe_scribe() → transcript
    ↓
Browser: textarea populated with transcript
```

### Frontend (induction_template.py)

Key functions: `toggleDictation()`, `startDictation()`, `stopDictation()`, `transcribeAudio()`

- `startDictation()`: requests `getUserMedia({audio: true})`, creates `MediaRecorder` with best supported MIME type (prefers `audio/webm;codecs=opus`), starts recording
- Chrome/Firefox: records as webm with opus codec (~10KB/s of speech)
- Safari: falls back to mp4 container
- Recording indicator: `.mic-btn.recording` CSS class with red pulse animation
- Graceful fallback: if `MediaRecorder` unsupported, shows chat message suggesting Chrome/Firefox/Edge
- Silent detection: blobs under 500 bytes rejected as "too short or silent"
- `transcribeAudio(blob)`: creates `FormData`, POSTs to `/api/induction/{id}/voice-transcribe`, appends transcript to textarea

### Backend (server.py)

`POST /api/induction/{tenant_id}/voice-transcribe`:
1. Validates tenant exists (404 if not)
2. Checks `scribe_available()` (503 if ELEVENLABS_API_KEY missing)
3. Validates content-type is audio/* (400 if not)
4. Rejects files under 100 bytes (400 "empty or too short")
5. Saves to temp file with correct extension (.webm/.ogg/.mp4/.mp3/.wav)
6. Calls `transcribe_scribe(temp_path)` from `scribe_stt.py`
7. Returns `{text, language, duration_seconds, segments}` or `{error}` on failure
8. Cleans up temp file in finally block

### Scribe v2 (scribe_stt.py)

- Provider: ElevenLabs Scribe v2 (`model_id=scribe_v2`)
- Supports 11 Indian languages + English
- Cost: $0.22/hr
- `is_available()`: checks ELEVENLABS_API_KEY in env
- `transcribe_scribe(audio_path, diarize=False)`: POSTs to ElevenLabs API, returns `{text, language, duration_seconds, segments}`

### Test Coverage

`tests/test_induction_voice.py` — 14 tests:
- Happy path: transcript returned with language + duration
- Silent recording: empty text → "No speech detected" note
- Short text: single char → "No speech detected"
- Scribe unavailable: 503
- Empty audio: under 100 bytes → 400
- No file: 422 (FastAPI validation)
- Invalid tenant: 404
- Unsupported format: text/plain → 400
- OGG/MP4 formats accepted
- Scribe error surfaces: 500 with error message
- Scribe exception handled: 500, temp file cleaned up
- Whitespace stripping

## Deprecated: Web Speech API (REMOVED June 2026)

The induction page previously used the browser-native `window.SpeechRecognition` / `webkitSpeechRecognition` API. This was removed because:

1. Safari never supported it — dead on arrival for iOS users
2. Chrome-only, English-only, no Indian language support
3. Zero test coverage — silently rotted for months
4. Error handling just showed "not supported in this browser" and users typed instead
5. No way to verify transcription quality or consistency

The old implementation used module-level variables (`recognition`, `isRecording`, `dictationText`) with auto-restart on silence. All of this was replaced by the MediaRecorder pipeline above.

### Migration Notes

- Function names `toggleDictation()`, `startDictation()`, `stopDictation()` were preserved for backward compatibility with the button's onclick handler
- The `micBtn` element ID and `.mic-btn` CSS class remain unchanged
- If reverting to browser speech for any reason, remember: `dictationText` MUST be module-level (not inside callback), and `getUserMedia` MUST run before creating `SpeechRecognition`
