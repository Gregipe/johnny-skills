# ElevenLabs TTS WebSocket — Correct Protocol & Auth Status

## Final Determination (July 3, 2026)

The ElevenLabs API key (`2e8145d489...`, 64-char hex) **DOES work** for TTS WebSocket.
Earlier failures were due to incorrect protocol — the WebSocket requires `generation_config`
in the first message to start audio generation.

### Correct WebSocket TTS Test

```python
import json
from websockets.sync.client import connect

KEY = os.environ['ELEVENLABS_API_KEY']
url = 'wss://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB/multi-stream-input?model_id=eleven_turbo_v2_5&output_format=pcm_16000'
ws = connect(url, additional_headers={'xi-api-key': KEY}, open_timeout=10)

# CRITICAL: first message MUST include generation_config
ws.send(json.dumps({
    'text': ' ',
    'try_trigger_generation': True,
    'generation_config': {'chunk_length_schedule': [50]},
}))

# Send actual text
ws.send(json.dumps({'text': ' Hello world.', 'try_trigger_generation': True}))
ws.send(json.dumps({'text': ''}))  # flush

# Receive audio (base64-encoded in JSON 'audio' field)
msg = json.loads(ws.recv(timeout=3))
print(f"Audio received: {len(msg['audio'])} chars base64")
# → Audio received: 51636 chars base64 ✅
```

### Key Insights

| Test | Approach | Result |
|------|----------|--------|
| TTS WebSocket w/ header auth only | connect + recv | Timeout (no welcome msg) |
| TTS WebSocket w/ header auth + text | send text → recv | Timeout (no generation_config → server ignores) |
| TTS WebSocket w/ header auth + generation_config | send init w/ generation_config → text → flush → recv | **Audio received ✅** |
| TTS WebSocket w/ body auth | xi_api_key in first message | "Invalid API key" (auth MUST be in header) |
| REST TTS endpoint | POST with xi-api-key header | 200 ✅ |
| STT WebSocket | connect + recv | session_started ✅ |

The original "Invalid API key" errors from direct testing were caused by:
1. Sending `xi_api_key` in the message body (not supported — must be header)
2. Not sending `generation_config` in the first message (server drops connection silently)

### What This Means for Pipecat

`ElevenLabsTTSService` (WebSocket) in Pipecat 1.4.0 handles the protocol correctly — it sends
the proper init sequence with `generation_config`. The service DOES work with Greg's key.

The earlier switching to `ElevenLabsHttpTTSService` was UNNECESSARY and caused a regression:
HTTP TTS broke the entire inference chain (no text, no audio). Root cause unconfirmed but
suspected to be the aiohttp session lifecycle or HTTP TTS frame format incompatibility with
the SmallWebRTC output transport.

### Recommendation

Use `ElevenLabsTTSService` (WebSocket) — the default in Pipecat templates. Only switch to
HTTP TTS if WebSocket is confirmed broken with a specific key. The July 3 auth investigation
was a false alarm — the WebSocket works.

## Original Investigation (superseded)

The initial investigation incorrectly concluded the key lacked WebSocket TTS permission.
The error was a protocol issue, not a permission issue. The key has full access.
