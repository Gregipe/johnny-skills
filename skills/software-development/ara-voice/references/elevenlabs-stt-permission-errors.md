# ElevenLabs Realtime STT — API Key Permission Errors

## Policy Violation (1008) on WebSocket Reconnect

**Observed: July 10, 2026 — ARA voice agent**

### Error trace

```
ERROR | pipecat.services.websocket_service:_verify_connection:64 - 
  ElevenLabsRealtimeSTTService#0 connection verification failed: 
  received 1008 (policy violation) invalid_request; 
  then sent 1008 (policy violation) invalid_request

ERROR | pipecat.services.websocket_service:_try_reconnect:105 - 
  ElevenLabsRealtimeSTTService#0 reconnection attempt 3 failed: 
  ElevenLabsRealtimeSTTService#0 websocket reconnection failed verification
```

### Root cause candidates

1. **Restricted API key scope** — Key `sk_808d0007...` had STT/TTS permissions only. `/v1/models` returned `missing_permissions: models_read`. `/v1/user` returned `missing_permissions: user_read`. The key works for WebSocket connections but specific parameters (like `keyterms`) may trigger a policy violation.

2. **`keyterms` parameter** — The `scribe_v2_realtime` model accepts `keyterms` for vocabulary bias. But a restricted key may not have permission for this feature. Removing `keyterms=stt_keyterms or []` and using `keyterms=[]` resolved the reconnect failures.

3. **Rate limiting from rapid reconnection** — When the pipeline fails initialization (e.g., FrameProcessor blocking StartFrame), the STT service reconnects 3 times with ~4s gaps. If all fail, the session ends. Multiple failed sessions in quick succession can trigger temporary rate limiting.

### Browser-side signals

```
[Debug] received message: user-started-speaking
[Debug] received message: user-stopped-speaking  
[Debug] received message: error — ElevenLabsRealtimeSTTService reconnection failed verification
[Debug] Remote track ended: microphone
[Debug] datachannel closed
```

### Fixes applied

1. Removed `keyterms` parameter from STT settings (set to `[]`)
2. Removed custom `FrameProcessor` that was blocking `StartFrame` and causing pipeline init failure → rapid reconnection cycle
3. Aligned ESM CDN versions to prevent client-js dual-version conflict

### Prevention

- Test new API keys with `curl https://api.elevenlabs.io/v1/models` before deploying
- Keep STT config minimal — only add parameters (`keyterms`, `language`, etc.) after confirming the key supports them
- Monitor `/var/log/ara-voice.log` for `policy violation` errors after any bot.py change
