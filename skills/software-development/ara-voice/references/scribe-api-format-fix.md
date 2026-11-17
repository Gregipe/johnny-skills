# Scribe v2 API Format Fix — June 25, 2026

## The Bug

`scribe_stt.py` sent audio as JSON with base64-encoded content:
```python
payload = {"audio_base64": audio_base64, "model_id": "scribe_v2", ...}
r = requests.post("https://api.elevenlabs.io/v1/speech-to-text", json=payload, ...)
```

ElevenLabs returned `422 Client Error: unknown`. The correct format is **multipart form upload**, not JSON.

## The Fix

```python
with open(audio_path, "rb") as fh:
    files = {"file": (os.path.basename(audio_path), fh, "audio/ogg")}
    form_data = {
        "model_id": "scribe_v2",
        "diarize": str(diarize).lower(),
        "tag_audio_events": "false",
    }
    r = requests.post(
        "https://api.elevenlabs.io/v1/speech-to-text",
        headers={"xi-api-key": key},
        files=files,
        data=form_data,
        timeout=120
    )
```

Key changes:
- `files=` instead of `json=` — uploads binary directly
- `data=` for form fields (not nested in JSON body)
- No `Content-Type: application/json` header — requests sets multipart automatically

## Root Cause

The ElevenLabs STT API endpoint (`POST /v1/speech-to-text`) expects:
- `file` — binary audio/video file as multipart form field
- Other params as form fields (`model_id`, `diarize`, `tag_audio_events`, `language_code`)

It does NOT accept base64-encoded audio in a JSON body. The `source_url` parameter exists for remote files, but the standard path is multipart upload.

## Module Location

`/opt/ara/scribe_stt.py` — `transcribe_scribe()` function
