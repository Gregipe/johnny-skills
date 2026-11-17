# ARA Voice Agent — Deployment Reference

## Architecture

```
Browser (dashboard)                        Hetzner (46.224.132.99)
  │                                          │
  ├─ GET /voice/start ──────────────────────►│ ara-server:8766
  │  (same-origin, no CORS)                  │   │
  │                                          │   ├─ POST /api/voice/session → voice_token
  │                                          │   │  (validates session cookie → tenant_id)
  │                                          │   │
  │  client-js PipecatClient                 │   ├─ GET /api/voice/tools?secret= → tool list
  │    SmallWebRTCTransport                  │   │
  │      WebRTC (STUN+TURN) ◄───────────────►│   └─ /voice/{path} ──proxy──► voice-agent:8768
  │                                          │                                │
  │  Audio: remote track →                    │     Pipecat 1.4.0               │
  │    browser speakers                       │     STT: ElevenLabs Scribe v2   │
  │                                          │     LLM: GPT-5.4-mini           │
  │                                          │     TTS: ElevenLabs Turbo v2.5   │
                                             │     VAD: Silero                  │
```

## Key URLs

| Endpoint | Method | Auth | Returns |
|----------|--------|------|---------|
| `/api/voice/session` | POST | session cookie | `{voice_token, expires_at}` |
| `/api/voice/tools?secret=` | GET | `?secret=ARA_VOICE_SECRET` | `{tools: [...]}` |
| `/api/voice/tool` | POST | `{"secret": "...", "tool": "...", "args": {...}, "tenant_id": "..."}` | ToolResult JSON |
| `/voice/start` | POST | none (proxy) | Pipecat session + SDP |
| `/voice/sessions/{id}/api/offer` | POST | none (proxy) | WebRTC answer |

## Server Files

| Path | Role |
|------|------|
| `/opt/ara/server.py` | ARA FastAPI — voice endpoints + `/voice/{path}` proxy |
| `/opt/ara/voice_endpoint_utils.py` | Voice session/tool auth helpers |
| `/opt/ara-voice-agent/bot.py` | Pipecat voice agent entry point |
| `/opt/ara-voice-agent/voice_tools.py` | Tool schema fetching + handler factory |
| `/opt/ara/.env` | `ARA_VOICE_SECRET=c0Q3G7cj...` |
| `/opt/ara-voice-agent/.env` | `ELEVENLABS_API_KEY=...`, `OPENAI_API_KEY=...`, `ARA_VOICE_SECRET=...` |

## TTS Voice

- **Voice:** Nisha (Indian accent) — ID: `XrExE9yKIg1WjnnlVkGX`
- **Model:** `eleven_turbo_v2_5`
- **Config:** `TTS_VOICE_ID` and `TTS_MODEL` env vars in `/opt/ara-voice-agent/.env`

## VAD Tuning

Current thresholds (balanced for noisy home/office):
```python
SileroVADAnalyzer(params=VADParams(
    confidence=0.7,     # unchanged from default
    start_secs=0.3,     # 300ms continuous speech (default 200ms)
    stop_secs=0.3,      # 300ms silence before turn ends (default 200ms)
    min_volume=0.65,    # ignore soft noise (default 0.6)
))
```

**Barge-in architecture note:** `allow_interruptions=True` uses RAW VAD output, NOT Smart Turn v3. Smart Turn only controls when your turn ENDS. This means VAD tuning is the ONLY lever for false barge-in interruptions.

**Echo diagnostic:** If bot cuts off mid-word (not mid-sentence), suspect acoustic echo (bot hears own TTS through speakers). Test with headphones — if interruptions stop, it's echo. If they continue, raise VAD thresholds.

**Browser fix:** Ensure `getUserMedia` includes echo cancellation:
```js
navigator.mediaDevices.getUserMedia({
  audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
});
```
Pipecat's SmallWebRTCTransport may not pass these by default — verify in browser DevTools under the `getUserMedia` call.

## Process Management

**⚠️ The voice agent has NO systemd service.** It runs as a manual process and dies on server reboot, OOM kill, or crash. Unlike `ara-server` and `ara-whatsapp-sidecar`, there is no `ara-voice-agent.service`.

**Starting manually:**
```bash
ssh root@46.224.132.99 'cd /opt/ara-voice-agent && source .venv/bin/activate && nohup python bot.py > /dev/null 2>&1 &'
```

**Checking if alive:**
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8768/
# 307 = running (redirects to client page), 000 = dead
```

**Symptoms when dead:**
- Dashboard voice button renders but clicking has no effect (no `PipecatClient` connection)
- Browser console shows WebSocket errors (no response from `/voice/start`)
- `lsof -i :8768` shows nothing

## GOTCHAs Discovered

1. **`?secret=` query param, NOT header.** ARA voice endpoints use `?secret=` and `"secret"` in JSON body. Headers like `X-Voice-Secret` are silently ignored.

2. **`params.arguments` can be dict.** Pipecat 1.4.0 with OpenAI models passes arguments as a `dict`, not a JSON string. Calling `json.loads()` on a dict → `TypeError: the JSON object must be str, bytes or bytearray, not dict`.

3. **`load_dotenv()` import order.** Module-level `os.getenv()` calls freeze values before dotenv runs. Pass secrets as function parameters instead.

4. **`runner_args.body` is SDP, not POST body.** Per-session data from `/start` POST is lost after WebRTC handshake. Use env vars or external store keyed by session_id.

5. **Audio routing in browser.** The Pipecat client's `SmallWebRTCTransport` needs `playoutElement` set for audio output. Without it, remote WebRTC tracks arrive but never play. Create the audio element during user click (autoplay policy).
