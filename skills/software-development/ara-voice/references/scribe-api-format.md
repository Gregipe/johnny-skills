# Scribe v2 API Format Fix — June 2026

## Problem
Initial integration sent audio as JSON with base64-encoded audio:
```python
payload = {"audio_base64": audio_base64, "model_id": "scribe_v2", ...}
r = requests.post("https://api.elevenlabs.io/v1/speech-to-text", json=payload, ...)
```
Returned **422 Client Error: unknown** — ElevenLabs expects multipart form upload, not JSON.

## Fix
Scribe v2 batch endpoint uses **multipart form** with the `file` field:
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

## Key params
- `model_id`: `"scribe_v2"` (batch) or `"scribe_v2_realtime"` (streaming)
- `diarize`: `"true"` or `"false"` (string, not boolean)
- `tag_audio_events`: `"false"` to suppress `[laughter]`, `[music]` tags
- `language_code`: optional ISO-639-1 code, auto-detected if omitted
- `entity_detection`: `"all"` or categories (30% surcharge)

## Response format
```json
{
  "language_code": "en",
  "language_probability": 1.0,
  "text": "Full transcript text...",
  "words": [
    {"text": "Hello", "start": 0.0, "end": 0.5, "type": "word", "speaker_id": "speaker_0"}
  ],
  "audio_duration": 120.5
}
```

## Cost
- Scribe v2 (batch): $0.22/hour (~₹18/hour, ₹0.30/min)
- Scribe v2 Realtime: $0.39/hour
- Diarization: included in base price
- Entity detection: +30% surcharge

## Indian Languages
Excellent (WER ≤5%): Kannada, Malayalam
High (5-10%): Hindi, Bengali, Gujarati, Marathi, Tamil, Telugu, Nepali, Odia
Good (10-20%): Assamese, Punjabi
Moderate (25-50%): Urdu, Sindhi

Improved Indic-English code-switching (English words in Latin script within Hindi/Telugu sentences).
