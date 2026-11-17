# ElevenLabs Voice Selection

This account's API key only has access to standard ElevenLabs voices. Custom/cloned voices do not exist in this workspace.

## Testing Voice Validity

Since the key lacks `voices:read` permission, the only way to test if a voice ID works is via REST TTS:

```python
import json, urllib.request
from pathlib import Path

# Load key from .env
env_path = Path("/opt/ara-voice-agent/.env")
for line in env_path.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

def test_voice(vid):
    body = json.dumps({
        "text": "Hello, testing voice.",
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
        data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req)
        audio = resp.read()
        return len(audio) > 100  # real audio, not error
    except Exception as e:
        return False  # 404 = voice doesn't exist
```

## Confirmed Valid Voices (July 3, 2026)

| Voice | ID | Notes |
|-------|-----|-------|
| Adam | `pNInz6obpgDQGcFmaJgB` | Current production voice |
| Nisha | `XrExE9yKIg1WjnnlVkGX` | Indian-sounding name, standard voice |
| Rachel | `21m00Tcm4TlvDq8ikWAM` | Standard voice |
| Domi | `AZnzlk1XvdvUeBnXmlld` | Standard voice |
| Bella | `EXAVITQu4vr4xnSDxMaL` | Standard voice |
| Elli | `MF3mGyEYCl7XYWbV9V6O` | Standard voice |
| Sam | `yoZ06aMxZJJ28mfd3POQ` | Standard voice |

## Confirmed Invalid

- `o6qTxWUeRyzRYZyUNDVJ` — user-provided, 404
- `cgSgspJ2msm6clMCkdWk` (Kajal) — 404
- `wjNabWGFxgrYZSyMGifq` (Priya) — 404
- `tQexICDQ7nuPhI8ucNQ4` (Lavanya) — 404
- `bEGm9fORLuI4US8kWNMw` (Ananya) — 404

## To Add Custom Indian/Hindi Voices

1. Go to ElevenLabs Dashboard → Voices → Add Voice
2. Upload samples or use Professional Voice Cloning
3. The cloned voice gets a new ID — test via REST TTS before deploying
4. Update `TTS_VOICE_ID` in `.env` or `bot.py` default
