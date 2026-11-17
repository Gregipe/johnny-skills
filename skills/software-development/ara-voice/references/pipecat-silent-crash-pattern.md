# Pipecat ElevenLabs TTS Settings Crash — Error Transcript

## The symptom

WebRTC connects successfully (ICE completed, tracks exchanged, browser shows "connected"). User speaks — absolutely zero audio response. No errors in browser console. `/start` returns `200 OK` with a session ID.

## The root cause

The bot subprocess crashes during pipeline initialization inside a background task. The runner silently swallows the error — the HTTP response is already sent before the bot starts.

## Error log (from /var/log/ara-voice.log)

```
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  ...
  File "/opt/ara-voice-agent/bot.py", line 117, in bot
    pipeline, transport = build_pipeline(runner_args, system_prompt)
  File "/opt/ara-voice-agent/bot.py", line 85, in build_pipeline
    settings=ElevenLabsTTSService.Settings(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: ElevenLabsTTSSettings.__init__() got an unexpected keyword argument 'output_format'
```

## What was wrong

```python
# BROKEN — output_format and optimize_streaming_latency are NOT valid Settings fields
tts = ElevenLabsTTSService(
    api_key=key,
    settings=ElevenLabsTTSService.Settings(
        voice=TTS_VOICE_ID,
        model="eleven_flash_v2_5",
        output_format="pcm_16000",           # ❌ doesn't exist here
        optimize_streaming_latency=4,        # ❌ HTTP TTS only
    ),
)
```

## The fix

```python
# CORRECT — sample_rate is a constructor param, voice/model are Settings
tts = ElevenLabsTTSService(
    api_key=key,
    sample_rate=16000,  # ← constructor param, NOT in Settings
    settings=ElevenLabsTTSService.Settings(
        voice=TTS_VOICE_ID,
        model="eleven_flash_v2_5",
    ),
)
```

## Valid ElevenLabsTTSSettings fields (Pipecat 1.4.0)

- `voice` (str) — voice ID
- `model` (str) — TTS model name
- `language` (Language | str | None)
- `stability` (float)
- `similarity_boost` (float)
- `style` (float)
- `use_speaker_boost` (bool)
- `speed` (float)
- `apply_text_normalization` ("auto" | "on" | "off")

NO: `output_format`, `optimize_streaming_latency`, `sample_rate`, `voice_id` (use `voice`)

## Detection pattern

This class of bug (silent pipeline crash) is detected by:
1. Checking server logs for `TypeError|AttributeError|Exception` AFTER a `/start` session
2. Pre-deployment constructor validation (see SKILL.md)
3. Must return ZERO errors — any error in background task = dead pipeline

## Other silent crash causes (same session)

1. `SmallWebRTCTransport.params()` — doesn't exist. Use `TransportParams()`.
2. `TransportParams()` — audio BOTH directions default to `False`. Must set `audio_in_enabled=True, audio_out_enabled=True`. This is the hardest to debug — no crash, no log, no error, just silence. Browser shows \"connected,\" bot-ready is received, but no audio flows.
3. `ElevenLabsRealtimeSTTService` model `scribe_v2` — wrong. Use `scribe_v2_realtime`.
4. `ElevenLabsTTSService` model `eleven_flash_v2_5` — wrong for WebSocket TTS. Use `eleven_turbo_v2_5`.
5. `WhatsAppTransport` — doesn't exist. Use `WhatsAppClient`.
