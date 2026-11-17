# Voice Notes → STT Pipeline (June 2026)

Voice-to-CRM via WhatsApp: agent sends a voice note → faster-whisper transcribes → Ava parses into structured CRM updates.

## Architecture

```
Agent sends voice note on WhatsApp
       ↓
Baileys sidecar: detect audioMessage, download Opus bytes
       ↓
POST as base64 to ARA /api/whatsapp/voice-inbound
       ↓
ARA saves .ogg to temp, runs faster-whisper base.en
       ↓
Transcript wrapped with field-report instruction
       ↓
Agent chat API → Ava extracts lead/action → executes CRM tools
       ↓
Confirmation sent back via WhatsApp
```

## Sidecar Changes (`whatsapp-sidecar/index.js`)

### Detection

In `messages.upsert`, before text processing:

```javascript
const hasAudio = !!msg.message?.audioMessage;
const isGroup = remoteJid.endsWith('@g.us');
if (hasAudio && !isGroup) {
  // Self-chat checks (same as text: fromMe, backlog, forwardedMsgIds)
  // ...
  sendAudioToARA(msg, ...);
  continue;
}
```

### Audio Download & Forward

Add `downloadContentFromMessage` to the Baileys import:

```javascript
const { ..., downloadContentFromMessage } = require('@whiskeysockets/baileys');
```

Helper function:

```javascript
async function sendAudioToARA(msg, phone, pushName, remoteJid) {
  try {
    // 1. Download decrypted audio bytes
    const stream = await downloadContentFromMessage(msg.message.audioMessage, 'audio');
    const chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    const audioBuffer = Buffer.concat(chunks);

    // 2. Base64 encode and POST to ARA voice endpoint
    const payload = JSON.stringify({
      phone, name: pushName,
      audio_base64: audioBuffer.toString('base64'),
      message_id: msg.key.id,
      remote_jid: remoteJid,
      duration_seconds: msg.message.audioMessage.seconds || 0,
    });

    const url = new URL(ARA_VOICE_URL);
    const req = http.request({ hostname: url.hostname, port: url.port, path: url.pathname,
      method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) }
    }, (res) => { /* handle response */ });
    req.on('error', (e) => logger.warn(`sendAudioToARA error: ${e.message}`));
    req.write(payload); req.end();
  } catch (e) {
    logger.warn(`sendAudioToARA error: ${e.message}`);
  }
}
```

The `ARA_VOICE_URL` constant (default `http://localhost:8766/api/whatsapp/voice-inbound`).

### Audio Format Notes

Baileys' `downloadContentFromMessage` for audio messages returns **raw Opus bytes** in an Ogg container — they ARE valid `.ogg` files already. No conversion needed. The sidecar base64-encodes them and ARA writes them directly as `.ogg`.

## ARA Voice Endpoint (`server.py`)

### Route

```python
@app.post("/api/whatsapp/voice-inbound")
def whatsapp_voice_inbound(data: dict):
    """Receive a voice note from the sidecar, transcribe, and route to Ava."""
    phone = data.get("phone", "")
    audio_b64 = data.get("audio_base64", "")
    message_id = data.get("message_id", "")
    remote_jid = data.get("remote_jid", "")

    if not audio_b64:
        return {"status": "error", "error": "no audio"}

    # Decode and save temp file
    audio_bytes = base64.b64decode(audio_b64)
    os.makedirs("/tmp/ara_voice", exist_ok=True)
    ogg_path = f"/tmp/ara_voice/{uuid.uuid4().hex}.ogg"
    with open(ogg_path, "wb") as f:
        f.write(audio_bytes)

    # Transcribe with faster-whisper
    transcript = _transcribe_audio(ogg_path)

    # Clean up temp file
    try: os.remove(ogg_path)
    except: pass

    if not transcript:
        return {"status": "ok", "transcript": "", "note": "empty transcription"}

    # Wrap with voice instruction and route to agent chat
    _process_voice_transcript(transcript, phone, message_id, remote_jid)
    return {"status": "ok", "transcript": transcript}
```

### Whisper Model (`_get_whisper_model`)

Lazy-loaded singleton — model loads on first voice note:

```python
_whisper_model = None

def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        import os as _os
        # HF_HUB_OFFLINE may be set globally (e.g. by Hermes sqlite-vec plugin)
        _old = _os.environ.pop("HF_HUB_OFFLINE", None)
        from faster_whisper import WhisperModel
        _log = logging.getLogger("whatsapp")
        _log.info("Loading faster-whisper model (base.en)...")
        _whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
        if _old is not None:
            _os.environ["HF_HUB_OFFLINE"] = _old
        _log.info("faster-whisper base.en loaded")
    return _whisper_model
```

**Why temporarily pop `HF_HUB_OFFLINE`:** The Hermes Agent profile sets `HF_HUB_OFFLINE=1` globally (via sqlite-vec plugin). faster-whisper needs to download the model from HuggingFace Hub on first load. Without clearing this var, the model download fails silently and the server crashes when processing the first voice note.

### Transcription

```python
def _transcribe_audio(ogg_path):
    model = _get_whisper_model()
    segments, info = model.transcribe(ogg_path, language="en", beam_size=5)
    return " ".join(seg.text for seg in segments).strip()
```

Uses `base.en` model — small, fast, English-only. For demos and initial deployment. Swap to `small.en`, `medium.en`, or `large-v3` for better accuracy.

### Voice Transcript Processing

```python
def _process_voice_transcript(transcript, phone, message_id, remote_jid):
    """Wrap transcript with field-report instructions and send to agent chat."""
    wrapped = (
        f"[AUDIO VOICE NOTE FROM FIELD AGENT]\n"
        f"Transcription: {transcript}\n\n"
        f"This is a field report from an agent on the ground. Your job is to:\n"
        f"1. Identify which lead/company they're talking about\n"
        f"2. Update the lead's notes with a structured visit summary\n"
        f"3. Extract any follow-up dates/times and schedule action items\n"
        f"4. Update the lead's stage if warranted\n"
        f"5. Confirm back concisely what you did\n\n"
        f"Treat this as a CRM-update instruction, not a conversation. "
        f"Do NOT ask follow-up questions — execute."
    )
    message_id_str = message_id or ""
    # Call agent chat API
    resp = requests.post(
        f"http://localhost:8766/api/agent/chat/{TENANT_ID}",
        json={"message": wrapped, "message_id": message_id_str},
        timeout=30,
    )
    if resp.ok:
        data = resp.json()
        ava_reply = data.get("response", "")
        if ava_reply:
            from whatsapp_sidecar_client import wa
            # Send formatted reply back via WhatsApp
            if remote_jid:
                formatted = f"🎙 *Voice Processed*\n\n" + ava_reply
                wa.send_to_jid(remote_jid, formatted)
```

## faster-whisper Installation

```bash
pip install faster-whisper
```

The `base.en` model (~150MB) downloads from HuggingFace Hub on first use and caches to `~/.cache/huggingface/hub/`. Subsequent loads are instant.

### Model Options

| Model | RAM | Speed | Accuracy | Use Case |
|-------|-----|-------|----------|----------|
| `base.en` | ~1.5GB | Fast | Good | Initial demo |
| `small.en` | ~2.5GB | Medium | Very good | Production English |
| `medium.en` | ~5GB | Slow | Excellent | High accuracy |
| `large-v3` | ~10GB | Slowest | Best | Multilingual + noisy audio |

Set via `WhisperModel("small.en", device="cpu", compute_type="int8")`. On an M5 MacBook Pro 32GB, even `medium.en` is viable.

## Ava Prompt Wrapper

The voice flow uses a **pre-prompt wrapper** — a structured instruction layer that wraps the raw transcript before sending to Ava's agent chat. This is NOT a permanent system prompt change. Ava's core personality stays the same; only voice messages get the structured extraction instruction.

The wrapper tells Ava to:
1. Identify the lead/company
2. Update notes with a visit summary
3. Extract follow-up dates and schedule action items
4. Update stage if warranted
5. Confirm back concisely

**Key design principle:** voice = task, text = conversation. The wrapper converts the transcript into a structured CRM-update instruction so Ava treats it as an action, not a chat.

## Testing

End-to-end verification (after setup):

```bash
# 1. Create a test audio file
ffmpeg -f lavfi -i "sine=frequency=220:duration=3" -ac 1 -ar 16000 -acodec libopus /tmp/test_voice.ogg

# 2. Base64 encode and POST
python3 -c "
import base64, json, urllib.request
with open('/tmp/test_voice.ogg', 'rb') as f:
    audio_b64 = base64.b64encode(f.read()).decode()
payload = json.dumps({'phone':'919582549236','name':'Owner',
    'audio_base64': audio_b64,
    'message_id':'test_001',
    'remote_jid':'919582549236@s.whatsapp.net',
    'duration_seconds':3}).encode()
req = urllib.request.Request(
    'http://localhost:8766/api/whatsapp/voice-inbound',
    data=payload,
    headers={'Content-Type':'application/json'}, method='POST')
resp = urllib.request.urlopen(req, timeout=120)
print(json.dumps(json.loads(resp.read()), indent=2))
"
```

Expected output for a pure-tone test: `{"status": "ok", "transcript": "You"}` (or similar hallucination from sine wave). With real speech, the transcript should be accurate within Whisper's known limitations.

## Pitfalls

- **HF_HUB_OFFLINE=1 blocks model download**: If `HF_HUB_OFFLINE=1` is set globally, faster-whisper can't download its model on first load. The `_get_whisper_model()` helper pops this var temporarily. If you're debugging a "Whisper model failed to load" error, check this env var first.
- **Model loads on first voice note, not server start**: The first voice note after server restart takes ~5s longer (model download + load). Subsequent notes are fast (~1-2s transcription time).
- **`.ogg` format only**: Baileys delivers audio as Ogg Opus. The endpoint expects this format. If the format changes (e.g., WhatsApp supports new codecs), the temp file extension and Whisper parameters may need updating.
- **Base64 overhead**: Base64 encoding adds ~33% size overhead. For a typical 30s audio note (~40KB Opus), the payload is ~55KB. Fine for JSON POST. If voice notes become longer or more frequent, switch to multipart upload.
- **Transcription quality depends on audio quality**: WhatsApp's audio compression (Opus at ~16kbps) is adequate for speech but loses detail on background noise, crosstalk, or low-volume speech. For noisy environments, consider enabling Voice Isolation on the agent's phone.
- **Swapping to OpenAI Whisper API**: Change `_transcribe_audio()` to call the API instead. The rest of the pipeline (wrapper, Ava processing, confirmation) stays identical.
