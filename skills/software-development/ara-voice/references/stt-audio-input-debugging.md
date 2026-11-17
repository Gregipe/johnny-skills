# STT Audio Input Debugging — Pipecat Cascade Pipeline

Diagnostic methodology for when a Pipecat cascade pipeline (STT→LLM→TTS) produces no response despite:
- WebRTC connection completing successfully (ICE connected, tracks exchanged)
- `bot-ready` received, data channel open
- STT WebSocket connecting and sessions starting
- TTS WebSocket connecting
- Pipeline links verified in logs
- `bot-interrupted` messages firing (VAD detects speech)

## The three-step isolation method

### Step 1: TTS-only bypass test

Isolate audio OUTPUT from input. Create a minimal bot that bypasses STT and LLM entirely:

```python
async def bot(runner_args):
    transport = SmallWebRTCTransport(
        webrtc_connection=runner_args.webrtc_connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True, audio_in_passthrough=True),
    )
    tts = ElevenLabsTTSService(api_key=key, sample_rate=16000, settings=...)
    pipeline = Pipeline([transport.input(), tts, transport.output()])
    
    worker = PipelineWorker(pipeline, params=PipelineParams(allow_interruptions=True))
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    
    # Speak after 2s
    async def speak():
        await asyncio.sleep(2)
        await worker.queue_frame(TTSSpeakFrame("Hello, this is a test. Can you hear me?"))
    asyncio.create_task(speak())
    await runner.run()
```

**If audio plays**: TURN relay + WebRTC output + TTS service are all working. Bug is in the audio INPUT path (browser mic → Pipecat transport → STT).
**If no audio**: Bug is in TURN/TTS/output. Fix those first before debugging STT.

### Step 2: Audio frame energy logging

Patch `SmallWebRTCInputTransport.read_audio_frame` in `pipecat/transports/smallwebrtc/transport.py` to log energy levels:

```python
# After the line: yield audio_frame
if not hasattr(self, "_frame_count"):
    self._frame_count = 0
self._frame_count += 1
if self._frame_count <= 5:
    import numpy as np
    arr = np.frombuffer(pcm_bytes, dtype=np.int16)
    energy = float(np.sqrt(np.mean(arr.astype(np.float64)**2)))
    logger.warning(f"AUDIO_FRAME #{self._frame_count}: {len(pcm_bytes)} bytes, energy={energy:.1f}")
```

**If energy < 50**: Browser mic is silent, muted, or not capturing. Check browser permissions.
**If 50 < energy < 500**: Mic is working but quiet. Check mic gain, turn off noise suppression.
**If energy > 500**: Audio is arriving with good energy. Bug is in the STT service or pipeline routing.

### Step 3: Diagnostic audio recorder

If frames have energy but STT produces no transcription, record raw PCM to a WAV file to verify frame contents:

```python
audio_chunks = []
start_recording = False

class AudioLogger(FrameProcessor):
    async def process_frame(self, frame, direction):
        if isinstance(frame, InputAudioRawFrame):
            arr = np.frombuffer(frame.audio, dtype=np.int16)
            energy = float(np.sqrt(np.mean(arr.astype(np.float64)**2)))
            logger.warning(f"🎤 AUDIO: {len(frame.audio)} bytes, energy={energy:.1f}")
            if energy > 50:
                start_recording = True
            if start_recording:
                audio_chunks.append(frame.audio)
        await super().process_frame(frame, direction)
```

Save to WAV after 12 seconds:
```python
async def save_audio():
    await asyncio.sleep(12)
    if audio_chunks:
        all_audio = b"".join(audio_chunks)
        wf = wave.open("/tmp/webrtc_audio.wav", "wb")
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(all_audio)
        wf.close()
```

### Step 3a: The passthrough trap

If Step 1 passes (TTS works) but Steps 2-3 show ZERO frames arriving at any downstream processor, the issue is `audio_in_passthrough=False`. Pipecat's RTVI processor consumes audio frames internally for VAD-based `bot-interrupted` detection. Without `audio_in_passthrough=True`, frames are never forwarded to the pipeline.

- **Symptom**: `bot-interrupted` messages fire (VAD detects speech), but no `InputAudioRawFrame` reaches STT
- **Symptom**: TTS-only bypass works (Step 1 passes), but full cascade is silent
- **Symptom**: `MediaStreamError` after ~50 seconds — audio track times out with no consumer
- **Fix**: Add `audio_in_passthrough=True` to `TransportParams()`

This was the 3+ hour root cause on July 3, 2026. Three separate TAs timed out without finding it. The tell was that `bot-interrupted` messages appeared (proving audio frames arrived at the transport and VAD processed them) but no transcription occurred (proving frames were consumed internally, never forwarded).

## Verified Pipecat 1.4.0 TransportParams defaults

| Param | Default | Effect when False |
|-------|---------|-------------------|
| `audio_in_enabled` | `False` | No audio input track created — total silence |
| `audio_out_enabled` | `False` | No audio output track created — TTS never heard |
| `audio_in_passthrough` | `False` | Audio frames consumed by RTVI, never reach STT |

All three must be `True` for a cascade STT→LLM→TTS pipeline.

## TURN server verification

If audio tracks exist but `MediaStreamError` fires within seconds, the issue is TURN relay. STUN alone (Google's public server) fails behind symmetric NAT:

1. Install coturn: `apt-get install -y coturn`
2. Configure `/etc/turnserver.conf` with long-term credentials
3. Patch Pipecat runner `iceServers` line (hardcoded at `pipecat/runner/run.py:636`)
4. Open ports 3478/udp, 3478/tcp, 5349/tcp
5. Verify: `echo test | nc -u -w2 <server-ip> 3478 && echo reachable`

**Tell**: Server logs show `typ relay` ICE candidates from your TURN server IP. Without TURN: only `typ host` and `typ srflx` candidates, and `MediaStreamError` fires within 13-20 seconds.
