---
name: pipecat-voice-agent
description: Pipecat 1.4.0 real-time voice agents — WebRTC, cascade pipeline, TURN.
---

# Pipecat Voice Agent

Build and debug real-time voice agents using Pipecat 1.4.0. Cascade pipeline (STT → LLM → TTS) over WebRTC with TURN relay.

## Prerequisites

- Pipecat 1.4.0+ installed (`pipecat-ai[webrtc]`)
- ElevenLabs API key (for STT or TTS)
- OpenAI API key (for LLM or STT)
- Python 3.11+
- TURN server for production (coturn recommended)

## Canonical Pipeline Pattern

Pipecat 1.4.0 uses `WorkerRunner` + `PipelineWorker`, NOT the deprecated `PipelineRunner`:

```python
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams
from pipecat.pipeline.worker import PipelineWorker
from pipecat.workers.runner import WorkerRunner
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.base_transport import TransportParams
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.aggregators.llm_context import LLMContext

def build_pipeline(runner_args):
    from pipecat.services.elevenlabs.stt import CommitStrategy
    from pipecat.turns.user_start import VADUserTurnStartStrategy
    from pipecat.turns.user_stop import SpeechTimeoutUserTurnStopStrategy
    from pipecat.turns.user_turn_strategies import UserTurnStrategies

    transport = SmallWebRTCTransport(
        webrtc_connection=runner_args.webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    )

    # STT with VAD commit (server-side commit, lower latency than MANUAL)
    stt = ElevenLabsRealtimeSTTService(
        api_key=ELEVENLABS_API_KEY,
        commit_strategy=CommitStrategy.VAD,
        settings=ElevenLabsRealtimeSTTService.Settings(
            model="scribe_v2_realtime",
            vad_silence_threshold_secs=0.5,
            vad_threshold=0.4,
        ),
    )

    llm = OpenAILLMService(
        api_key=OPENAI_API_KEY,
        settings=OpenAILLMService.Settings(
            model="gpt-5.4-mini",
            system_instruction="You are a helpful voice assistant.",
            temperature=0.3,  # lower temperature for voice → faster TTFT
        ),
    )

    tts = ElevenLabsTTSService(
        api_key=ELEVENLABS_API_KEY,
        sample_rate=16000,
        settings=ElevenLabsTTSService.Settings(
            voice="pNInz6obpgDQGcFmaJgB",
            model="eleven_turbo_v2_5",
            speed=1.1,
            stability=0.5,
            similarity_boost=0.75,
        ),
    )

    # CRITICAL: LLMContextAggregatorPair converts TranscriptionFrame → LLMMessagesFrame
    # VAD-only turn start (no TranscriptionUserTurnStartStrategy → prevents echo interruptions)
    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(
                    confidence=0.7,
                    start_secs=0.2,
                    stop_secs=0.2,
                    min_volume=0.6,
                )
            ),
            user_turn_stop_timeout=1.0,
            user_turn_strategies=UserTurnStrategies(
                start=[VADUserTurnStartStrategy()],
                stop=[SpeechTimeoutUserTurnStopStrategy(
                    user_speech_timeout=0.6,
                    wait_for_transcript=True,
                )],
            ),
        ),
    )

    pipeline = Pipeline([
        transport.input(),      # WebRTC audio in
        stt,                    # Speech-to-text
        user_aggregator,        # VAD + TranscriptionFrame → LLMMessagesFrame
        llm,                    # LLM response
        tts,                    # Text-to-speech
        transport.output(),     # WebRTC audio out
        assistant_aggregator,   # Captures assistant responses for conversation context
    ])

    return pipeline, transport

async def bot(runner_args):
    pipeline, transport = build_pipeline(runner_args)
    worker = PipelineWorker(pipeline, params=PipelineParams(
        allow_interruptions=True,
        enable_metrics=True,
        enable_usage_metrics=True,
    ))
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    await runner.run()
```

## Required Pipeline Stages

Every cascade voice pipeline MUST have these stages, in order:

| Position | Stage | Purpose |
|----------|-------|---------|
| 1 | `transport.input()` | WebRTC audio input |
| 2 | STT service | Speech-to-text transcription |
| 3 | `user_aggregator` | VAD + TranscriptionFrame → LLMMessagesFrame |
| 4 | LLM service | Text response generation |
| 5 | TTS service | Text-to-speech synthesis |
| 6 | `transport.output()` | WebRTC audio output |
| 7 | `assistant_aggregator` | Captures responses for conversation context |

## Common Pitfalls

### 1. Missing LLMContextAggregatorPair — SILENT FAILURE
**Symptom:** STT transcribes correctly (committed transcripts appear in logs), but LLM never responds. No errors.
**Root cause:** `TranscriptionFrame` from STT doesn't get converted to `LLMMessagesFrame` that the LLM can process.
**Fix:** Add `LLMContextAggregatorPair` between STT and LLM. Without it, transcription frames flow through but the LLM ignores them.

### 2. Missing VAD — STT never commits
**Symptom:** STT connects but no transcription appears. Audio arrives at transport but STT produces nothing.
**Root cause:** ElevenLabs Scribe v2 Realtime needs `VADUserStoppedSpeakingFrame` to send its WebSocket commit message that finalizes transcription. Without VAD, audio streams to ElevenLabs but segments are never committed.
**Fix:** `LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer())` provides VAD. The `LLMContextAggregatorPair` bundles this.

### 3. TransportParams audio defaults — SILENT
**Symptom:** WebRTC connects, everything looks right, but no audio in either direction. No errors.
**Root cause:** `TransportParams()` defaults to `audio_in_enabled=False` and `audio_out_enabled=False`. Audio is completely disabled.
**Fix:** Explicit `TransportParams(audio_in_enabled=True, audio_out_enabled=True)`.

### 4. audio_in_passthrough defaults to True (Pipecat 1.4.0)
This was NOT the root cause. `audio_in_passthrough` already defaults to `True` in Pipecat 1.4.0 and governs whether audio flows past the STT, not whether STT runs. Audio was arriving correctly the whole time. The real issue was missing VAD + context aggregator.

### 5. Deprecated PipelineRunner
**Symptom:** Pipeline starts but services (STT, LLM, TTS) never initialize. No service logs.
**Root cause:** `PipelineRunner` is deprecated since Pipecat 1.3.0. Use `PipelineWorker` + `WorkerRunner`.
**Fix:** Replace `PipelineTask` + `PipelineRunner` with `PipelineWorker` + `WorkerRunner`.

### 6. gpt-5.4-mini rejects max_tokens
**Symptom:** LLM returns HTTP 400: "Unsupported parameter: 'max_tokens' is not supported with this model."
**Fix:** Omit `max_tokens` from `OpenAILLMService.Settings`. The model uses `max_completion_tokens` internally.

### 7. ElevenLabs API key — REST vs WebSocket permissions
ElevenLabs keys can have different permissions for REST vs WebSocket. A key that works for REST TTS (HTTP 200) may still fail for WebSocket TTS. The same key may work for STT WebSocket but not TTS WebSocket — or vice versa.
**Test:** Directly test WebSocket connections with `websockets` library before assuming the key is valid.

**Also — `keyterms` parameter causes 1008 policy violation with restricted keys:**
If the WebSocket connects, then immediately disconnects with `received 1008 (policy violation) invalid_request`, the `keyterms` parameter in `ElevenLabsRealtimeSTTService.Settings` may be the cause. Restricted API keys (STT/TTS only) reject vocabulary/keyterms injection. Fix: use `keyterms=[]` instead of `keyterms=stt_keyterms or []`, or upgrade to an unrestricted key.

**Diagnostic:** 
```bash
# Test if the key is restricted
curl -s "https://api.elevenlabs.io/v1/user" -H "xi-api-key: $KEY"
# Restricted → "missing the permission user_read"
# Unrestricted → returns user info

# Check STT connection failures in voice logs  
grep "1008\|policy violation\|reconnection.*fail" /var/log/ara-voice.log
```

### 8. WebRTC audio track dies (MediaStreamError)
**Symptom:** After ~50 seconds: "Media stream error while reading the audio; clearing track." No audio frames arrive.
**Root cause:** UDP media blocked behind NAT/firewall. STUN alone insufficient for symmetric NAT.
**Fix:** Deploy a TURN server (coturn) and inject it into the Pipecat runner's ICE config at `pipecat/runner/run.py`:
```python
IceServer(urls=["turn:46.224.132.99:3478?transport=udp"],
          username="turnuser", credential="<secret>"),
```

### 8a. Custom FrameProcessor Blocks System Frames — Pipeline Never Initializes

**Symptom:** Adding a custom `FrameProcessor` (e.g. `SilentReasoningGate`) between LLM and TTS breaks the entire pipeline. Logs show:
```
ERROR | SilentReasoningGate#1 Trying to process InputAudioRawFrame but StartFrame not received yet
```
Repeated for every audio frame. STT connects and disconnects in a loop. `bot-ready` never fires. Session dies with idle timeout.

**Root cause:** Custom `FrameProcessor.process_frame()` must pass ALL system frames through with `await self.push_frame(frame, direction)`. Even if the override correctly pushes most frames, the Pipecat lifecycle may trip on `StartFrame` ordering — audio frames arrive before pipeline initialization completes.

**Fix — remove the custom processor and use prompt-based silence instead:**
The system prompt telling the LLM to "STAY SILENT during tool calls" is sufficient for most cases. A hard FrameProcessor gate is only needed when the LLM consistently ignores the prompt. If you must use one, ensure:

```python
async def process_frame(self, frame, direction):
    # Only block text/speech during tool calls
    if self._tools_in_flight > 0 and isinstance(frame, (LLMTextFrame, TTSSpeakFrame, TextFrame)):
        return  # drop
    # Push EVERYTHING else — including StartFrame, EndFrame, CancelFrame, AudioRawFrame, MetricsFrame
    await self.push_frame(frame, direction)
```

**Verification:** After removing/adding a FrameProcessor, check the voice log for `StartFrame not received yet` errors. If present, the processor is blocking system frames.

## TURN Server Setup

```bash
apt-get install -y coturn
# Config: /etc/turnserver.conf
listening-port=3478
relay-ip=<PUBLIC_IP>
external-ip=<PUBLIC_IP>
realm=<realm>
lt-cred-mech
user=turnuser:<secret>
# Open firewall
ufw allow 3478/udp
ufw allow 3478/tcp
```

The Pipecat runner hardcodes `stun:stun.l.google.com:19302` with no TURN. Patch `pipecat/runner/run.py` line ~636 to add the TURN server.

### 19. `SmallWebRTCTransport.connect()` — `body:` parameter silently dropped

**Symptom:** JS calls `pcClient.connect({ endpoint: '/voice/start', body: JSON.stringify({ voice_token: token }) })`. The voice agent's `/start` endpoint receives an empty body. Server log: `ERROR: Failed to parse request body: Expecting value: line 1 column 1 (char 0)`. The session still starts (WebRTC connects, STT works), but `bot-ready` never fires and the UI stays on "connecting" forever.

**Root cause:** The `body:` parameter in `SmallWebRTCTransport.connect()` is NOT forwarded as the HTTP POST body to the `/start` endpoint. The Pipecat JS client (`@pipecat-ai/client-js` ≥ 1.11) uses `body:` as the `sessionId` for internal URL construction (replacing `/start` with `/sessions/{sessionId}/api/offer`). The actual POST to `/start` contains only the WebRTC SDP offer, not the application-level body.

**Fix:** Do NOT rely on `connect()`'s `body:` parameter for transmitting session data. Instead:
- **Option A (single-tenant):** Skip per-session auth entirely. Use environment variables or hardcoded secrets in the voice agent. No token needed.
- **Option B (multi-tenant):** Pass the token as a query parameter on the endpoint URL: `endpoint: '/voice/start?token=' + encodeURIComponent(token)`. Read from `request.query_params` in the voice agent's `/start` handler.
- **Option C:** Use the RTVI `client-ready` message to transmit session data. The Pipecat client sends `client-ready` with `about:` metadata. Extend the `setAboutClient()` call before `connect()` to include the token, then read from `request_data.get("about", {})` in the server.

**Diagnostic:** Check the voice agent log for `Failed to parse request body`. If present AND `bot-ready` never fires despite `client-ready` arriving, the body is empty. Verify by adding `logger.debug(f"request_data: {request_data}")` after the `request.json()` call in the `/start` handler.

### 20. "Stuck at Connecting" — Systematic Diagnostic Flow

When the voice UI stays on "connecting" and never transitions to "listening", follow this flow in order:

1. **Check voice agent process:** `ps aux | grep bot.py` — is it running?
2. **Check voice agent logs:** `tail -f /var/log/ara-voice.log` — look for the session timeline
3. **Verify WebRTC:** `ICE connection state is completed` + `Connection state changed to: connected` — if missing, connectivity/TURN issue
4. **Verify STT:** `Connected to ElevenLabs Realtime STT` — if missing, API key or network issue
5. **Verify client-ready:** `Received client-ready: version 2.0.0` — if missing, PipecatJS handshake failure (CORS, proxy, version mismatch)
6. **Check for `bot-ready` emission:** Server should send `BOT_READY` RTVI message after pipeline init. If client-ready arrived but `bot-ready` didn't fire, the RTVI config is incomplete — check the `/start` request body (see pitfall 19).
7. **Check for body parse errors:** `Failed to parse request body` — if present, the proxy or client is not forwarding the POST body (see pitfall 19)
8. **Check for JS errors:** `typeof window.toggleVoiceMode` should return `"function"`. If `"undefined"`, the module script failed to load (check esm.sh imports)
9. **Check for silent JS crashes:** If `toggleVoiceMode` IS a function but clicking does nothing, a `ReferenceError` inside `startVoiceMode()` is being caught by try/catch (see pitfall 17 — `btn` vs `voiceBtn`)

The critical decision point: if STT transcribed the user's voice but the LLM never responded, the pipeline is initialized but `bot-ready` blocked the output chain. This is the body-forwarding issue (pitfall 19) or the event-handler race (pitfall 21).

### 21. `bot-ready` never fires despite `client-ready` arriving — event handler race

**Symptom:** Pipeline fully initializes (StartFrame reaches end, WebRTC connected, STT transcribes user speech), `client-ready` is received (`Received client-ready: version 2.0.0`), but `bot-ready` is never sent. UI stays on \"connecting\" forever. 26+ second gap in logs between `client-ready` and user speech with zero activity. No errors or warnings.

**Root cause:** The `PipelineWorker`'s automatic `on_client_ready` → `set_bot_ready()` event handler chain silently fails. The handler IS registered (line ~409-412 of `pipecat/pipeline/worker.py`), and `_handle_client_ready` DOES call `set_client_ready()` which calls `_call_event_handler(\"on_client_ready\")`, but the handler callback never executes. This appears to be a race condition or event-loop issue in Pipecat 1.4.0.

**Fix — force `bot-ready` with a background task.** Add this in `bot()` after `runner.add_workers(worker)` and before `runner.run()`:

```python
import asyncio

# After: await runner.add_workers(worker)
# Before: await runner.run()

async def _force_bot_ready():
    await asyncio.sleep(3)
    if worker.rtvi and not worker.rtvi._bot_ready:
        logger.warning(\"bot-ready not sent automatically - forcing it\")
        await worker.rtvi.set_bot_ready()
asyncio.create_task(_force_bot_ready())
```

The 3-second delay ensures the pipeline (WebRTC, STT WebSocket, Smart Turn, TTS) is fully initialized before forcing `bot-ready`. The check `not worker.rtvi._bot_ready` prevents double-sending if the automatic handler eventually fires.

**Diagnostic:** Check logs for `client-ready` followed by complete silence until user speech. If no `bot-ready` log appears and no errors are present, the event handler didn't fire. The forced task will log `\"bot-ready not sent automatically - forcing it\"` when it activates.

### 24. Port drift: bot.py port changed → ARA proxy still hardcoded to old port

**Symptom:** Dashboard voice button clicks to "connecting" then immediately disappears. Voice agent log shows no incoming request.

**Root cause:** bot.py changed its listening port (e.g., from 8768 to 7860), but /opt/ara/server.py has a hardcoded proxy URL. The ARA server proxies /voice/* to localhost:{old_port}, which fails.

**Fix:** Update the proxy URL in server.py and any other hardcoded references:
```bash
grep -rn "localhost:8768\|localhost:7860" /opt/ara/server.py /opt/ara-voice-agent/
```

### 25. Shared .env overwrite kills sibling services (CRITICAL)

**Symptom:** After deploying a new service that shares .env with an existing service, the existing service crashes with `OpenAIError: Missing credentials` on next use.

**Root cause:** Replacing the entire .env file wiped the OPENAI_API_KEY used by bot.py. Both services share the same .env but need different vars.

**Fix:** Never replace a shared .env. Always append with `>>`. Before editing, dump existing keys:
```bash
grep "_API_KEY\|_TOKEN" /opt/ara-voice-agent/.env
```
When adding new vars, use `cat >> file << "EOF"`, not write_file or scp.

## References

- `references/ara-search-enhancements.md` — Phonetic matching, space normalization, and action enrichment for lead search (July 2026)
- `references/ara-deployment.md` — ARA-specific architecture, deployment details, endpoint reference
- `references/echo-cancellation.md` — Browser-level echo cancellation patterns
- `references/latency-audit-2026-07-04.md` — Full latency audit with prioritized optimizations (July 2026)
- `references/whatsapp-calling-infra.md` — WhatsApp Cloud API calling integration: WhatsAppClient, FastAPI webhooks, per-call pipelines, CRM context injection
- `references/model-router-pattern.md` — Config-driven, env-var-swappable LLM provider selection for voice agents (Groq/DeepInfra/Vertex/OpenAI)


### 26. Voice agent restart — must kill + restart after any voice_tools.py or bot.py change

**Symptom:** Fixed code is on disk but the voice agent still exhibits old behavior. `voice_confirm` tool appears registered in code but isn't available to the LLM.

**Root cause:** The bot process loads `voice_tools.py` and `bot.py` into memory at startup. Code changes on disk after startup have no effect until the process is restarted. Unlike the ARA server (systemd-managed), the voice agent runs as a bare process.

**Fix:**
```bash
# Must use separate kill + start steps — pkill with background start has race conditions
pkill -f "bot.py" 2>/dev/null
sleep 2
/opt/ara-voice-agent/.venv/bin/python /opt/ara-voice-agent/bot.py >> /var/log/ara-voice.log 2>&1 &
sleep 5
ss -tlnp | grep 7860  # verify it's listening
```

**Verification:** Check the PID start time is after the file modification time:
```bash
ps -p $(pgrep -f "bot.py") -o lstart=
ls -l /opt/ara-voice-agent/voice_tools.py
```

### 27. Write handler must return pending_id — description is NOT the ID

**Symptom:** Voice write confirmation works in server curl tests but fails in live voice sessions. LLM calls `voice_confirm` with the human-readable description as `pending_id` instead of the UUID.

**Log signature (broken):**
```
voice_confirm called with: pending_id = "➕ Add lead: Moksh Malji (HDFC Bank) — shall I create it?"
```

**Log signature (correct):**
```
voice_confirm called with: pending_id = "93b6d059"
```

**Root cause:** The write tool handler in `voice_tools.py` was returning only the description text from the server's stage response. The actual `pending_id` UUID was in the server response (`data.get("pending_id", "")`) but wasn't included in the result string returned to the LLM.

**Fix — handler must embed the pending_id:**
```python
if data.get("ok"):
    pending_id = data.get("pending_id", "")
    desc = data.get("description", "")
    result = (
        f"STAGED pending_id={pending_id}\n"
        f"Description: {desc}\n"
        f"Read the Description back to the user VERBATIM. "
        f"When they say 'confirm', call voice_confirm(cancel=false, pending_id=\"{pending_id}\"). "
        f"When they say cancel/no, call voice_confirm(cancel=true, pending_id=\"{pending_id}\")."
    )
```

**Detection:** Search the voice agent log for `voice_confirm` calls:
```bash
grep "voice_confirm.*pending_id" /var/log/ara-voice.log
```
If `pending_id` values are long sentences (>20 chars) rather than 8-char hex UUIDs, the handler is broken.

**Auto-cancel bug:** The `/api/voice/stage` endpoint originally cancelled ALL previous voice-pending actions before creating a new one. This meant staging action 2 silently killed action 1. The fix: remove the auto-cancel block so multiple pending actions can coexist. When confirming, the LLM calls `voice_confirm` for each `pending_id` individually.

### 27. System prompt variable injection — use .replace(), NOT .format()

**Symptom:** Bot crashes with `KeyError` or `NameError` when injecting dynamic values (like today's date) into `DASHBOARD_SYSTEM_PROMPT`.

**Root cause:** Using Python's `.format(today=...)` on a large triple-quoted string that may contain other `{` characters (JSON examples, code snippets, f-string-like patterns). Any unescaped `{` or `}` triggers a `KeyError`.

**Fix — use `.replace()` instead:**
```python
# ❌ Crashes on any stray { or } in the prompt
system_prompt = DASHBOARD_SYSTEM_PROMPT.format(today=today_str)

# ✅ Safe — only replaces the explicit placeholder
system_prompt = DASHBOARD_SYSTEM_PROMPT.replace("{today}", today_str)
```

**Backup-file trap:** When rolling back to a backup file, verify the backup HAS the same imports as the current code. A backup from a different version may have different import lines — a `replace()` targeting a specific `import` string will silently fail, leaving `datetime` imported but `NameError` at runtime.

**Prevention:** After any rollback + re-patch sequence, verify with `py_compile.compile()` before restarting the bot.

### 28. TTS markdown — ABSOLUTE RULE in system prompt (not a soft suggestion)

**Symptom:** ElevenLabs TTS stumbles on `**Devashish**` (reads as "asterisk asterisk Devashish asterisk asterisk"), emojis, and bullet lists with `*` or `-`.

**Root cause:** LLMs default to markdown formatting in structured output. Even a "no markdown" note in the system prompt is ignored when the LLM presents structured data (brain dumps, search results, action summaries).

**Fix — ABSOLUTE RULE with examples:**
```
ABSOLUTE RULE: Never use **, *, or emojis. Write everything as plain spoken sentences.
Use numbers ("first, second"), not asterisks for lists.
TTS must pronounce every character you output.
```

**Do NOT** use a soft suggestion ("Spoken-style output: no markdown"). The LLM ignores soft suggestions. "ABSOLUTE RULE" with explicit consequences (TTS pronunciation) works.

### 29. New conversational modes — gate behind explicit triggers, NEVER bake into main prompt

**Symptom:** Adding a "brain dump mode" instruction ("LISTEN SILENTLY — do NOT respond to individual points") to the main `DASHBOARD_SYSTEM_PROMPT` broke ALL voice conversations. The LLM stayed silent for every interaction, not just brain dumps.

**Root cause:** The "LISTEN SILENTLY" instruction was triggered by words the user might say in any context. The LLM misinterpreted normal conversation as brain dump mode and refused to respond.

**Fix:** New modes MUST be gated behind EXPLICIT trigger phrases that don't appear in normal conversation. Examples:
- ✅ `"Hey Ava, brain dump"` — unlikely to be said accidentally
- ✅ `"Ava, let me do a brain dump"` — explicit invocation
- ❌ `"share updates"`, `"think out loud"`, `"random chat"` — appear in normal speech

**Also:** New modes should live in separate system prompt branches (e.g., `BRAIN_DUMP_SYSTEM_PROMPT`), not in the main prompt. The LLM switches prompts when the trigger word is detected.

### 30. Patch-verify-restart chain for voice agent (CRITICAL)

**Symptom:** Code changes to `voice_tools.py` or `bot.py` appear correct on disk but the voice agent shows old behavior. The LLM calls tools the old way, `voice_confirm` isn't available, or the new system prompt isn't active.

**Root cause chain (any ONE of these breaks the fix):**
1. **Patch didn't apply** — The `patch` or `replace()` command silently failed. Check file content after patching.
2. **Bot not restarted** — The process has old code in memory. Always kill + restart after ANY change to bot.py or voice_tools.py.
3. **Bot not restarted correctly** — `pkill` + background start has race conditions. Verify the PID with `ss -tlnp | grep 7860`.
4. **Bot running stale code** — If the PID started before the file was modified, it has old code. Compare `ps -p <pid> -o lstart=` against `ls -l` file mtime.

**Full verification chain:**
```bash
# 1. Verify patch on disk
grep "EXPECTED_STRING" /opt/ara-voice-agent/voice_tools.py

# 2. Kill + restart (SEPARATE commands — pkill with bg start has races)
pkill -f "bot.py" 2>/dev/null; sleep 2
# If pkill fails (exit 255), use the two-step:
# Step A: ssh root@HOST '/opt/ara-voice-agent/.venv/bin/python /opt/ara-voice-agent/bot.py >> /var/log/ara-voice.log 2>&1 &'
# Step B: sleep 5 && ssh root@HOST 'ss -tlnp | grep 7860'

# 3. Verify new PID started AFTER the file change
echo "File mtime: $(ssh root@HOST 'ls -l /opt/ara-voice-agent/voice_tools.py | cut -d" " -f6-8')"
echo "PID start: $(ssh root@HOST 'ps -p $(pgrep -f "bot.py") -o lstart=')"

# 4. Verify port is actually listening
ssh root@HOST 'ss -tlnp | grep 7860'
```

**When restart fails (exit code 255):** This is a known SSH race condition. The `pkill` kills the SSH session itself if the shell's argv matches the pattern. Use two separate commands: kill in one, start in another. See the full restart recipe in #26.

### 31. Phonetic matching fallback for STT mis-transcriptions

**Symptom:** STT transcribes "Rameez" as "Ramiz." The exact-search `search_leads` returns zero results. Ava says "No lead named Ramiz found."

**Fix — consonant-skeleton + difflib fallback:**
Add a `_phonetic_match()` helper that matches when exact search returns nothing. Uses two strategies:
1. **Consonant skeleton:** Strip vowels, compare consonant sequence. "Rameez" → "rmz", "Ramiz" → "rmz" — identical.
2. **difflib.SequenceMatcher:** Ratio-based similarity with 0.6 threshold.

```python
def _phonetic_match(query: str, names: list[str], threshold: float = 0.6) -> list[str]:
    from difflib import SequenceMatcher
    import re
    def _skeleton(s: str) -> str:
        return re.sub(r'[aeiou]', '', s.lower())
    q_skel = _skeleton(query)
    matches = []
    for name in names:
        n_skel = _skeleton(name)
        skel_match = (q_skel == n_skel and len(q_skel) >= 2)
        ratio = SequenceMatcher(None, query.lower(), name.lower()).ratio()
        if skel_match or ratio >= threshold:
            matches.append((name, max(1.0 if skel_match else 0, ratio)))
    matches.sort(key=lambda x: x[1], reverse=True)
    return [m[0] for m in matches[:5]]
```

**Where to apply:** Both the voice tool handler (`elif tool_name == "search_leads"`) AND the REST API (`def search_leads(q, db)`) need the fallback. They are separate code paths in `server.py` — fixing one without the other leaves the other broken.

**Result annotation:** When a phonetic match is used, annotate the result with `[phonetic match: heard 'Ramiz']` so the LLM can say "I heard Ramiz — did you mean Rameez?"

### 32. Space-normalized lead name search for Indian names

**Symptom:** "Ram Gopal Nanda" (with space) returns zero results but "Ramgopal Nanda" (without space) exists. Common for Indian compound names.

**Root cause:** SQL `ILIKE '%Ram Gopal%'` doesn't match `'Ramgopal'` because the space is part of the pattern.

**Fix — normalize spaces before comparison:**
```python
from sqlalchemy import func

query_norm = query.replace(" ", "")  # "Ram Gopal" → "RamGopal"
leads = db.query(Lead).filter(
    Lead.name.ilike(f"%{query}%") |                              # exact match
    func.replace(Lead.name, " ", "").ilike(f"%{query_norm}%") |  # space-normalized
    func.replace(Lead.company, " ", "").ilike(f"%{query_norm}%") # company too
)
```

**Must be applied to BOTH search paths:**
- Voice tool handler: `elif tool_name == "search_leads"` in `server.py`
- REST API: `def search_leads(q, db)` in `server.py`

### 33. Action enrichment in lead search results

**Symptom:** Ava searches for a lead, says "no pending actions," user says "I thought there was a follow-up," Ava searches again and finds it. Two round trips when one should suffice.

**Fix:** Include pending action counts in search results:
```python
pending_count = db.query(ActionItem).filter(
    ActionItem.ref_id == lead.id,
    ActionItem.execution_state.in_(["pending", "staged", "in_progress"]),
).count()
action_note = f" | Actions: {pending_count} pending" if pending_count > 0 else " | No pending actions"
```

### 34. STT keyterms — inject lead names as ElevenLabs vocabulary bias

**Symptom:** ElevenLabs Scribe transcribes lead names incorrectly even after multiple correct pronunciations. "Sarin" → "Shireen," "Rameez" → "Ramiz."

**Root cause:** Scribe has no context about what names are likely to appear in the conversation. It defaults to open-ended transcription without domain-specific vocabulary.

**Fix — pass lead names as `keyterms` in STT Settings:**
```python
# Fetch lead names from ARA at session start
resp = await http.get(f"{ARA_BASE}/api/tenants/{tenant_id}/leads")
leads = resp.json()
stt_keyterms = [l["name"] for l in leads if l.get("name")]
# Also add first-name-only variants
for name in list(stt_keyterms):
    parts = name.split()
    if len(parts) > 1:
        stt_keyterms.extend(parts)
stt_keyterms = list(set(stt_keyterms))[:100]  # dedupe, max 100

# Pass to STT
stt = ElevenLabsRealtimeSTTService(
    settings=ElevenLabsRealtimeSTTService.Settings(
        keyterms=stt_keyterms,  # biases Scribe toward these words
    ),
)
```

**Keyterms limit:** 100 terms max, 50 chars each. First names (e.g., "Ramgopal" → also "Ram") help match partial-name utterances.

### 36. Rollback trap — backup files may be from a DIFFERENT version (CRITICAL)

**Symptom:** Restoring `bot.py.bak-phase2-pre` to undo a brain-dump prompt change silently wipes ALL Phase 2 features — confirmation flow, write tools, voice_confirm, enhanced system prompt. Bot still runs but behaves like Phase 1 (\"I can't make changes by voice yet\").

**Root cause:** The backup was created BEFORE Phase 2 was implemented. The filename `bak-phase2-pre` was misleading — it means \"pre-Phase 2\", i.e., the state BEFORE Phase 2. Rolling back to it destroyed weeks of work.

**Fix — ALWAYS check backup content before restoring:**
```bash
grep \"voice_confirm\|CONFIRMATION FLOW\" /path/to/backup.py
```
If the grep returns nothing, the backup is from a pre-Phase-2 era. Do NOT restore it.

**Prevention:** After every successful feature deployment, create a fresh backup with the CURRENT date:
```bash
cp bot.py bot.py.bak.$(date +%Y%m%d_%H%M%S)
```

**Recovery (when backup is stale):** Reconstruct the full system prompt from context. The `DASHBOARD_SYSTEM_PROMPT` is the single most load-bearing piece of configuration — losing it silently removes voice write capabilities, confirmation flow, and all persona rules. When rebuilding, verify with:
```bash
grep -c \"voice_confirm\|CONFIRMATION\|SILENT REASONING\" bot.py
# Expected: >= 3 matches

### 35. Silent reasoning mode — system prompt + dashboard feed + audio cue (Phase 1)

**Problem:** Ava narrates every tool call via TTS ("Let me search for that lead... Found them... Let me check the pipeline..."). Each utterance adds 1-3s latency. Users hear procedural narration they don't care about.

**Solution — four-layer implementation:**

**Layer 1: System prompt instruction (USELESS with DeepSeek)**
Prompt-only silence instructions are ignored by conversational LLMs. Do not rely on them alone.

**Layer 2: NarrationGate FrameProcessor (STRUCTURAL FIX — only reliable approach)**
Insert a `FrameProcessor` between LLM and TTS that marks narration text with `skip_tts=True`. Pipecat's TTS services already check this field. Two critical v2 fixes: (a) buffer 20+ chars before deciding narration vs response (streaming small chunks like "Got" appear first), (b) add standalone acknowledgment patterns ("Got it.", "Okay.") — not just patterns requiring specific continuations. Narration text still reaches dashboard display but never goes to TTS. See `ara-voice-calling` skill → `references/narration-gate-processor.md` for the full implementation.

**Layer 3: Dashboard thinking feed UI**
Add a `<div id="voiceThinkingFeed">` that shows real-time tool calls using RTVI events.

**Layer 4: Audio cue during processing**
Web Audio API subtle hum (180Hz sine at 3% volume) during tool execution.

**Layer 1: System prompt instruction**
```
SILENT REASONING MODE (CRITICAL)
You work in SILENT REASONING mode. Do NOT narrate your process.
Do NOT speak while calling tools or waiting for results.
Your thinking appears on the dashboard — the user can see it.
Only speak when:
- You have a final answer to deliver
- You need the user to confirm a write action
- You genuinely need to ask a clarifying question
- You're greeting the user or wrapping up
```

**Layer 2: Dashboard thinking feed UI**
Add a `<div id="voiceThinkingFeed">` that shows real-time tool calls:
```javascript
function addThinkingEntry(toolName) {
  const label = TOOL_CHIPS[toolName] || toolName;
  const div = document.createElement('div');
  div.innerHTML = '<span class="thinking-spinner"></span><span>' + label + '</span>';
  thinkingFeed.appendChild(div);
}
function completeThinkingEntry(toolName) {
  // Replace spinner with green checkmark ✓
}
```

Hook into existing RTVI events: `llmFunctionCallStarted` → add feed entry, `llmFunctionCallStopped` → mark complete, `botStartedSpeaking` → clear feed.

**Layer 3: Audio cue during processing**
Web Audio API subtle hum (180Hz sine at 3% volume) plays during thinking:
```javascript
function startAudioCue() {
  const ctx = new AudioContext();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = 'sine'; osc.frequency.value = 180;
  gain.gain.value = 0.03;
  osc.connect(gain).connect(ctx.destination);
  osc.start();
}
```

### 37. SilentReasoningGate — hard-block TTS during tool calls (Phase 2)

**Problem:** The LLM may ignore the \"SILENT REASONING MODE\" system prompt instruction and still emit text during tool calls. Prompt-only gates are fragile.

**Fix — FrameProcessor gate between LLM and TTS:**
```python
from pipecat.processors.frame_processor import FrameProcessor

class SilentReasoningGate(FrameProcessor):
    def __init__(self):
        super().__init__()
        self._tools_in_flight = 0

    async def process_frame(self, frame, direction):
        from pipecat.frames.frames import (
            FunctionCallsStartedFrame, FunctionCallResultFrame,
            LLMTextFrame, TTSSpeakFrame, TextFrame, TTSTextFrame,
        )
        if isinstance(frame, FunctionCallsStartedFrame):
            self._tools_in_flight += 1
        if isinstance(frame, FunctionCallResultFrame):
            self._tools_in_flight = max(0, self._tools_in_flight - 1)
        if self._tools_in_flight > 0 and isinstance(frame, (LLMTextFrame, TTSSpeakFrame, TextFrame, TTSTextFrame)):
            return  # drop — don't let TTS speak during tool calls
        await self.push_frame(frame, direction)
```

Insert between LLM and TTS in pipeline:
```python
pipeline = Pipeline([
    transport.input(), stt, user_aggregator,
    llm,
    SilentReasoningGate(),  # ← hard gate
    tts,
    transport.output(), assistant_aggregator,
])
```

**Import:** `FrameProcessor` must be imported explicitly — it's not auto-available:
```python
from pipecat.processors.frame_processor import FrameProcessor
```

**FULL report level:** Set `function_call_report_level="FULL"` in `TransportParams()` to include tool arguments and results in RTVI events, enabling richer dashboard thinking feed labels (e.g., \"Looking up leads: Rameez\" instead of just \"Looking up leads\").

See `references/ara-search-enhancements.md` for the full server-side implementation of pitfalls 31-33.

**Symptom:** Adding a "brain dump mode" instruction ("LISTEN SILENTLY — do NOT respond to individual points") to the main `DASHBOARD_SYSTEM_PROMPT` broke ALL voice conversations. The LLM stayed silent for every interaction, not just brain dumps.

**Root cause:** The "LISTEN SILENTLY" instruction was triggered by words the user might say in any context. The LLM misinterpreted normal conversation as brain dump mode and refused to respond.

**Fix:** New modes MUST be gated behind EXPLICIT trigger phrases that don't appear in normal conversation. Examples:
- ✅ `"Hey Ava, brain dump"` — unlikely to be said accidentally
- ✅ `"Ava, let me do a brain dump"` — explicit invocation
- ❌ `"share updates"`, `"think out loud"`, `"random chat"` — appear in normal speech

**Also:** New modes should live in separate system prompt branches (e.g., `BRAIN_DUMP_SYSTEM_PROMPT`), not in the main prompt. The LLM switches prompts when the trigger word is detected.

### 30. Patch-verify-restart chain for voice agent (CRITICAL)

**Symptom:** Code changes to `voice_tools.py` or `bot.py` appear correct on disk but the voice agent shows old behavior. The LLM calls tools the old way, `voice_confirm` isn't available, or the new system prompt isn't active.

**Root cause chain (any ONE of these breaks the fix):**
1. **Patch didn't apply** — The `patch` or `replace()` command silently failed. Check file content after patching.
2. **Bot not restarted** — The process has old code in memory. Always kill + restart after ANY change to bot.py or voice_tools.py.
3. **Bot not restarted correctly** — `pkill` + background start has race conditions. Verify the PID with `ss -tlnp | grep 7860`.
4. **Bot running stale code** — If the PID started before the file was modified, it has old code. Compare `ps -p <pid> -o lstart=` against `ls -l` file mtime.

**Full verification chain:**
```bash
# 1. Verify patch on disk
grep "EXPECTED_STRING" /opt/ara-voice-agent/voice_tools.py

# 2. Kill + restart (SEPARATE commands — pkill with bg start has races)
pkill -f "bot.py" 2>/dev/null; sleep 2
# If pkill fails (exit 255), use the two-step:
# Step A: ssh root@HOST '/opt/ara-voice-agent/.venv/bin/python /opt/ara-voice-agent/bot.py >> /var/log/ara-voice.log 2>&1 &'
# Step B: sleep 5 && ssh root@HOST 'ss -tlnp | grep 7860'

# 3. Verify new PID started AFTER the file change
echo "File mtime: $(ssh root@HOST 'ls -l /opt/ara-voice-agent/voice_tools.py | cut -d" " -f6-8')"
echo "PID start: $(ssh root@HOST 'ps -p $(pgrep -f "bot.py") -o lstart=')"

# 4. Verify port is actually listening
ssh root@HOST 'ss -tlnp | grep 7860'
```

**When restart fails (exit code 255):** This is a known SSH race condition. The `pkill` kills the SSH session itself if the shell's argv matches the pattern. Use two separate commands: kill in one, start in another. See the full restart recipe in #26.

### 27. Write handler must return pending_id — description is NOT the ID

**Symptom:** Voice write confirmation works in server curl tests but fails in live voice sessions. LLM calls `voice_confirm` with the human-readable description as `pending_id` instead of the UUID.

**Log signature (broken):**
```
voice_confirm called with: pending_id = "➕ Add lead: Moksh Malji (HDFC Bank) — shall I create it?"
```

**Log signature (correct):**
```
voice_confirm called with: pending_id = "93b6d059"
```

**Root cause:** The write tool handler in `voice_tools.py` was returning only the description text from the server's stage response. The actual `pending_id` UUID was in the server response (`data.get("pending_id", "")`) but wasn't included in the result string returned to the LLM.

**Fix — handler must embed the pending_id:**
```python
if data.get("ok"):
    pending_id = data.get("pending_id", "")
    desc = data.get("description", "")
    result = (
        f"STAGED pending_id={pending_id}\n"
        f"Description: {desc}\n"
        f"Read the Description back to the user VERBATIM. "
        f"When they say 'confirm', call voice_confirm(cancel=false, pending_id=\"{pending_id}\"). "
        f"When they say cancel/no, call voice_confirm(cancel=true, pending_id=\"{pending_id}\")."
    )
```

**Detection:** Search the voice agent log for `voice_confirm` calls:
```bash
grep "voice_confirm.*pending_id" /var/log/ara-voice.log
```
If `pending_id` values are long sentences (>20 chars) rather than 8-char hex UUIDs, the handler is broken.

See `references/voice-confirm-debugging.md` for the full debugging transcript.

1. `VADProcessor: User started speaking` (VAD fires)
2. `VADProcessor: User stopped speaking` (utterance end)
3. `Committed transcript: [...]` (STT produces text)
4. `OpenAILLMService: Generating chat from context [...]` (LLM called)
5. TTS audio sent to browser (user hears response)

If VAD fires but no transcript follows → STT commit issue. If transcript appears but no LLM → missing context aggregator. If LLM fires but no audio → TTS or output transport issue.

## ElevenLabs STT Details

`ElevenLabsRealtimeSTTService` extends `WebsocketSTTService`. It sends a **commit message** to the WebSocket on `VADUserStoppedSpeakingFrame` (confirmed at `elevenlabs/stt.py:693`). The commit is what tells ElevenLabs to finalize transcription. Without VAD, audio streams but never commits → no transcription.

The `ElevenLabsSTTService` (non-realtime, `scribe_v2` model) extends `SegmentedSTTService` and also needs VAD to know when to run batch transcription.

### 11. Bot gets cut off mid-sentence — false interruptions

**Symptom:** Bot says a few words ("Vinay") then stops. User has to say "go on" to resume. Happens repeatedly. Server logs show `broadcasting interruption` events. Client logs show `bot-interrupted` firing on filler words and ambient noise.

**Architectural insight:** `allow_interruptions=True` (barge-in) uses **raw VAD output**, NOT Smart Turn. Smart Turn v3 only controls turn END detection (when you've finished speaking). Barge-in fires on ANY VAD activation while the bot is talking — even a keyboard click or breathing.

**Three distinct causes, in order of likelihood:**

**A. Acoustic echo (speakers → mic feedback)** — MOST COMMON
Bot speaks through speakers → room mic picks it up → VAD calls it "user speech" → `bot-interrupted`. This is Pipecat issue #188 ("Interrupted by itself when speaker on").
**Quick diagnostic:** Use headphones. If interruptions stop instantly, it's echo. If they continue, it's VAD sensitivity.
**Fixes:**
- Use headphones (eliminates the acoustic path)
- Browser-level echo cancellation: `getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })`
- Pipecat's `InputAudioProcessorFilter` with echo cancellation

**B. VAD thresholds too low** — ambient noise triggers false speech
Room noise (fans, AC, keyboard, breathing) crosses VAD threshold. `start_secs` too low means short sounds trigger.
**Fix:** Aggressive thresholds:
```python
from pipecat.audio.vad.vad_analyzer import VADParams
vad_analyzer=SileroVADAnalyzer(
    params=VADParams(
        confidence=0.7,
        start_secs=0.6,   # require 600ms continuous speech (filters clicks/pops)
        stop_secs=0.3,    # Smart Turn wants SHORT stop_secs
        min_volume=0.85,  # echo from speakers is quieter than direct speech
    )
)
```
Pass this to `LLMUserAggregatorParams(vad_analyzer=...)`.

**C. The user's own filler words** ("Oh", "um", "ha ha")
These ARE genuine speech, so the VAD correctly triggers. But they're not actual interruptions.
**Fix:** LLM-based "selective refusal" — Pipecat CEO Kwindla Kramer's technique: prompt the LLM to output a special token when it detects that the interruption was non-substantive, so the bot resumes speaking.

**Interim workaround:** Set `allow_interruptions=False` in `PipelineParams`. Bot finishes speaking before listening. Not ideal UX but eliminates false interruptions entirely for Phase 1.

**IMPORTANT:** When using Pipecat ≥ 1.4.0 with ElevenLabs Realtime STT, barge-in may use `TranscriptionUserTurnStartStrategy` (NOT VAD). See pitfall 14. Echo cancellation at the audio level is required; VAD tuning alone won't fix it. See `references/echo-cancellation.md` for the browser-level getUserMedia monkey-patch.

### 14. `TranscriptionUserTurnStartStrategy` bypasses VAD for barge-in

**Symptom:** Bot still cuts off mid-sentence even after aggressive VAD tuning (high start_secs, high min_volume). Logs show:
```
User started speaking (strategy: TranscriptionUserTurnStartStrategy#0)
broadcasting interruption
```
The interruption fires on `TranscriptionUserTurnStartStrategy`, NOT on VAD activation.

**Root cause:** Pipecat's default `UserTurnStrategies` uses `TranscriptionUserTurnStartStrategy` as the turn START trigger when transcription is available (Pipecat ≥ 1.4.0). Any text the STT produces — including garbled echo transcribed as random characters, or partial/filler transcriptions — immediately fires `bot-interrupted`. The `vad_analyzer` in `LLMUserAggregatorParams` only controls turn END detection, not barge-in.

**This means** SileroVADAnalyzer params (`start_secs`, `min_volume`, `confidence`) have NO EFFECT on barge-in behavior. Echo cancellation at the audio level is the only fix.

**Secondary issue:** ElevenLabs Scribe v2 Realtime has its OWN VAD built into the WebSocket connection (server-side config: `vad_threshold=0.4`, `vad_silence_threshold_secs=1.5`, `min_speech_duration_ms=100`). This can produce `UserStartedSpeakingFrame` events that conflict with SileroVADAnalyzer — both detect \"speech\" independently.

**Diagnostic:** Check the strategy name in logs. If it says `TranscriptionUserTurnStartStrategy` or `TranscriptionUserTurnStopStrategy`, the VAD is NOT the gate. Audio-level echo fixes are required.

**Fixes:**
1. **Custom `UserTurnStrategies`** — override the default to use VAD-based start:
   ```python
   from pipecat.turns.user_turn_strategies import UserTurnStrategies
   from pipecat.turns.vad_based_user_turn_strategies import VADUserTurnStartStrategy
   user_params=LLMUserAggregatorParams(
       user_turn_strategies=UserTurnStrategies(
           start=[VADUserTurnStartStrategy()],
       ),
       vad_analyzer=SileroVADAnalyzer(params=VADParams(start_secs=0.6, min_volume=0.85)),
   )
   ```
2. **Browser echo cancellation** — inject into `getUserMedia` via monkey-patch BEFORE Pipecat imports (it calls `getUserMedia` internally):
   ```javascript
   (function() {
     var OrigGUM = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
     navigator.mediaDevices.getUserMedia = function(constraints) {
       if (!constraints) constraints = { audio: true };
       if (constraints.audio === true) constraints.audio = {};
       if (constraints.audio && typeof constraints.audio === 'object') {
         constraints.audio.echoCancellation = true;
         constraints.audio.noiseSuppression = true;
         constraints.audio.autoGainControl = true;
       }
       return OrigGUM(constraints);
     };
   })();
   ```
3. **Headphones** — eliminates acoustic echo entirely. Recommended for development/testing.

### 15. Twenty-Second Latency: Normal Pipeline Budget (defaults — FIXABLE)

**Symptom:** User says "Hey there" and first TTS response arrives ~20 seconds later. Logs show a 30-second gap between WebRTC connect and first LLM response.

**This is the DEFAULT budget — the canonical pattern above OPTIMIZES it.** With defaults:
- ElevenLabs STT WebSocket connect + first audio → transcription: ~5-10s
- Smart Turn v3 analyzing 8 seconds of audio before declaring turn end: ~2-3s
- Smart Turn timeout waiting for silence before declaring user finished: ~3-8s (configurable)
- LLM tool call round-trip (get_summary → ARA HTTP → return): ~2-3s
- LLM generation: ~1s
- TTS generation + first audio frame: ~0.3s
**Total: ~15-25 seconds.**

**With optimized config (canonical pattern above): ~3-5s.** Key changes:
- VAD-only turn start (no TranscriptionUserTurnStartStrategy → no echo interruptions)
- SpeechTimeoutUserTurnStopStrategy (no 8s Smart Turn ONNX window)
- VAD: `start_secs=0.2, stop_secs=0.2` (was 0.6/0.3)
- STT: `CommitStrategy.VAD` (was MANUAL)
- `user_turn_stop_timeout=1.0` (was 2.0)
- LLM: `temperature=0.3` (was 0.7)
- TTS: `speed=1.1` (was default)
- `allow_interruptions=False` (temporary: no echo-triggered false barge-ins)

See `references/latency-audit-2026-07-04.md` for full breakdown.

### 17. Dashboard inline JS — wrong variable name (`btn` vs `voiceBtn`) causes silent button failure

**Symptom:** Mic button in the dashboard chat input appears but clicking does nothing. No errors in browser console (caught by try/catch). Voice never activates.

**Root cause:** In the inline `<script type="module">` in `dashboard_template.py`, `setVoiceState('connecting')` references `btn.setAttribute(...)` but the variable defined at the top of the script is `voiceBtn` (from `document.getElementById('voiceBtn')`). `btn` is undefined → `ReferenceError` → caught by `startVoiceMode()`'s try/catch → `endVoiceMode()` resets to idle.

**Fix:** Replace `btn.setAttribute(...)` with `voiceBtn.setAttribute(...)` in the `connecting` branch of `setVoiceState()`:

```javascript
} else if (state === 'connecting') {
    voiceBtn.setAttribute('data-status', 'Connecting to voice agent...');  // NOT btn
    statusChip.textContent = 'Connecting...';
```

**Diagnostic:** Check `typeof window.toggleVoiceMode` in browser console. If `"function"` but button click does nothing, this variable typo is the likely cause. The function IS exposed globally — the crash happens inside it.

### 18. Duplicate `bot-llm-text` event handler overwrites transcript display

**Symptom:** Voice pipeline works (STT → LLM → TTS, audio plays) but transcript text never appears in `#chatMessages`. No errors.

**Root cause:** Two `pcClient.on('bot-llm-text', ...)` handlers registered in `startVoiceMode()`. The second (empty) handler at the end of the setup block overwrites the first one that creates DOM elements and appends text. Pipecat's event system uses last-registered-wins for handlers of the same event name.

**Fix:** Delete the duplicate. Only keep the first handler that creates `div.voice-transcript-line` elements and appends to `chatMsg`:

```javascript
// KEEP THIS ONE — creates transcript DOM elements
pcClient.on('bot-llm-text', (e) => {
    if (e.text) {
        const div = document.createElement('div');
        div.className = 'voice-transcript-line';
        div.textContent = 'Ava: ' + e.text;
        chatMsg.appendChild(div);
        chatMsg.scrollTop = chatMsg.scrollHeight;
    }
});

// DELETE THIS ONE — overwrites the handler above
// pcClient.on('bot-llm-text', (e) => {
//     // also show user transcript — handled separately via client-js events
// });
```

### 16. `child_timeout_seconds` for subagent delegation

Hermes config key `delegation.child_timeout_seconds` controls subagent timeout. Default 600s (10 min). For deep analysis tasks with `reasoning_effort: high` models (like glm-5.2), 600s is too short — each API call can take 30s+ due to reasoning overhead. Increase to 1800s (30 min) for research-oriented subagents. Set via `hermes config set delegation.child_timeout_seconds 1800`.

### 22. Pipecat JS event listeners MUST use camelCase — kebab-case handlers silently NEVER fire

**Symptom:** All Pipecat client-js event handlers registered with kebab-case strings (`pcClient.on('bot-ready', ...)`, `pcClient.on('bot-llm-text', ...)`, `pcClient.on('bot-started-speaking', ...)`) never fire. The UI stays on "connecting" forever. No errors in browser console — just silence.

**Root cause:** The Pipecat RTVI **wire protocol** uses kebab-case message types (`"type": "bot-ready"`, `"type": "bot-llm-text"`), but the `@pipecat-ai/client-js` library **translates** wire messages to camelCase **event names** before emitting. The `RTVIEvent` enum maps: `RTVIEvent["BotReady"] = "botReady"`, `RTVIEvent["BotLlmText"] = "botLlmText"`, `RTVIEvent["BotStartedSpeaking"] = "botStartedSpeaking"`, etc.

**EVERY event listener in dashboard JS MUST use camelCase.** The complete mapping:

| Wire type (kebab-case) | JS event name (camelCase) |
|---|---|
| `bot-ready` | `botReady` |
| `bot-connected` | `botConnected` |
| `bot-disconnected` | `botDisconnected` |
| `error` | `error` (no change) |
| `bot-started-speaking` | `botStartedSpeaking` |
| `bot-stopped-speaking` | `botStoppedSpeaking` |
| `user-transcription` | `userTranscript` |
| `bot-llm-text` | `botLlmText` |
| `bot-llm-started` | `botLlmStarted` |
| `bot-llm-stopped` | `botLlmStopped` |
| `bot-tts-text` | `botTtsText` |
| `bot-tts-started` | `botTtsStarted` |
| `bot-tts-stopped` | `botTtsStopped` |
| `user-started-speaking` | `userStartedSpeaking` |
| `user-stopped-speaking` | `userStoppedSpeaking` |
| `llm-function-call-started` | `llmFunctionCallStarted` |
| `llm-function-call-stopped` | `llmFunctionCallStopped` |

**Diagnostic:** Add `console.log` to each handler. If the log never appears, the event name is wrong. Check the actual enum values in the client-js source (`RTVIEvent` object exported from `@pipecat-ai/client-js`).

### 23. `botLlmText` fires per-token/word — accumulate text, do NOT create per-event divs

**Symptom:** Chat shows each word on a separate line:
```
Ava: I
Ava: can
Ava: hear
Ava: you
```

**Root cause:** Each `botLlmText` event delivers a partial text fragment (word or sub-word). Creating a new `<div>` per event produces one line per word. Pipecat streams LLM tokens as they arrive; the first event might be "I", the second " can", the third " hear", etc.

**Fix — accumulate in a single div:** Track a `currentBotLine` reference. On first `botLlmText`, create the div and seed it with the label. On subsequent events, append to `textContent`. On `botStoppedSpeaking`, clear the reference so the next response starts a fresh line.

```javascript
let currentBotLine = null;

pcClient.on('botLlmText', (e) => {
    if (e.text) {
        if (!currentBotLine) {
            currentBotLine = document.createElement('div');
            currentBotLine.className = 'voice-transcript-line';
            currentBotLine.textContent = 'Ava: ';
            chatMsg.appendChild(currentBotLine);
        }
        currentBotLine.textContent += e.text;
        chatMsg.scrollTop = chatMsg.scrollHeight;
    }
});

// Clear reference on botStoppedSpeaking so next response gets a fresh div
pcClient.on('botStoppedSpeaking', () => {
    currentBotLine = null;
    setVoiceState('listening');
});
```

**Why not use `botStartedSpeaking` to finalize the line?** `botLlmText` fires BEFORE `botStartedSpeaking` (text is generated first, then TTS begins). So the full text has already arrived by the time `botStartedSpeaking` fires. Clearing on `botStoppedSpeaking` is correct — it signals the end of the bot's turn, so the next utterance starts a new line.

### 12. `runner_args.body` is WebRTC SDP — NOT the `/start` POST body
**Symptom:** Any per-session data (tokens, tenant_id) passed in the `/start` POST body never reaches `bot()`. Reading `runner_args.body` gives WebRTC SDP data.
**Root cause:** Pipecat stores `/start` body → `active_sessions[session_id]`, then overwrites `runner_args.body` with WebRTC offer's SDP when creating `SmallWebRTCRunnerArguments`. The `/start` body is permanently lost to `bot()` after the WebRTC handshake.
**Fix:** Never read per-session data from `runner_args.body`. Use environment variables, an external store keyed by `session_id`, or skip per-session auth for single-tenant setups.

### 13. `load_dotenv()` import order — env vars must be set BEFORE module-level `os.getenv()` calls
**Symptom:** API calls return 401 even though `.env` has correct secrets. Printing `os.getenv("SECRET")` shows empty string.
**Root cause:** Python executes `os.getenv()` at module import time. If a module like `voice_tools.py` has `ARA_VOICE_SECRET = os.getenv("ARA_VOICE_SECRET", "")` at the top, and `load_dotenv()` runs AFTER that import, the variable is permanently empty.
**Fix:** Import order matters:
```python
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
from voice_tools import build_voice_tools  # imports AFTER dotenv runs
```
Prefer passing secrets as function parameters (`build_voice_tools(http, secret=SECRET)`) instead of relying on module-level env vars. This eliminates the timing dependency entirely.

### 10. CORS blocks dashboard → Pipecat direct calls
**Symptom:** Browser console shows "Origin X is not allowed by Access-Control-Allow-Origin". Voice never connects.
**Root cause:** Dashboard is served from one origin (e.g. `https://ara.example.com`) but tries to fetch Pipecat at a different origin (e.g. `https://ngrok-url.ngrok-free.dev/start`). Browsers block cross-origin fetches to different hosts.
**Fix:** Add a proxy route in the main application server to forward `/voice/*` requests to Pipecat on localhost. The dashboard calls `/voice/start` (same-origin) and the server proxies to `http://localhost:8768/start`. This elimates CORS entirely.
```python
# FastAPI proxy pattern
@app.api_route("/voice/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def voice_proxy(path: str, request: Request):
    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        body = await request.body()
        headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
        resp = await client.request(
            method=request.method, url=f"http://localhost:8768/{path}",
            headers=headers, content=body or None,
        )
        return Response(content=resp.content, status_code=resp.status_code,
                        headers=dict(resp.headers))
```

## Tool Calling with LLMContext

Pipecat 1.4.0 supports function/tool calling via `LLMContext(tools=[...])`:

```python
from pipecat.adapters.schemas.function_schema import FunctionSchema

# Build tools
tools = [
    FunctionSchema(
        name="search_leads",
        description="Search CRM leads. Args: {\"query\": \"...\"}",
        properties={"query": {"type": "string"}},
        required=["query"],
        handler=make_handler("search_leads"),
    ),
]

# Pass to LLMContext — tools are auto-registered, no separate call needed
context = LLMContext(tools=tools)

# Pass app_resources to PipelineWorker — available as params.app_resources in handlers
worker = PipelineWorker(pipeline, params=PipelineParams(...),
                        app_resources={"tenant_id": "x", "http_client": http})
```

Tool handlers receive `FunctionCallParams`:
```python
async def handler(params: FunctionCallParams) -> None:
    # params.arguments can be dict OR JSON string — handle both
    args = params.arguments
    if isinstance(args, str):
        import json; args = json.loads(args)
    if not isinstance(args, dict):
        args = {}
    http = params.app_resources["http_client"]
    result = await http.post(url, json={"tool": tool, "args": args})
    await params.result_callback(result["summary"])  # feeds result to LLM → TTS
```

**Pitfall: `params.arguments` type varies** — Pipecat 1.4.0 can pass arguments as a `dict` (from newer OpenAI models) OR a JSON `str` (from older models). Always check `isinstance(args, str)` before calling `json.loads()`, otherwise you get `"the JSON object must be str, bytes or bytearray, not dict"`. The safe pattern is shown above.

**Pitfall:** `FunctionSchema(handler=...)` auto-registers — do NOT call a separate `register_function()`. The handler kwarg exists at `adapters/schemas/function_schema.py:38`.

**Pitfall:** `app_resources` is passed to `PipelineWorker(...)`, NOT to `LLMContext(...)`. The handler receives it via `params.app_resources`.

**Pitfall: Secret injection for tool HTTP calls** — avoid module-level `os.getenv()` in tool modules (e.g. `voice_tools.py`). The variable is frozen at import time, before `load_dotenv()` runs. Instead, pass secrets as function parameters:
```python
# In bot.py (after load_dotenv):
secret = os.getenv("MY_SECRET", "")
tools = await build_tools(http, secret=secret, tenant_id=tenant_id)

# In voice_tools.py:
def make_handler(name, secret, tenant_id):
    async def handler(params):
        resp = await http.post(url, json={"secret": secret, "tenant_id": tenant_id})
```
This eliminates race conditions between dotenv loading and module import order.

## Useful Commands

```bash
# Test ElevenLabs TTS directly (REST)
curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB/stream" \
  -H "xi-api-key: $KEY" -H "Content-Type: application/json" \
  -d '{"text":"Hello world","model_id":"eleven_turbo_v2_5"}' --output test.mp3

# List ElevenLabs voices (requires voices:read permission)
curl -s "https://api.elevenlabs.io/v1/voices" -H "xi-api-key: $KEY"

# Check TURN server reachability
echo "test" | nc -u -w2 <TURN_IP> 3478 && echo "UDP OK"
```

## ARA Voice Agent (Hetzner)

See `references/ara-deployment.md` for ARA-specific architecture, deployment details, endpoint reference, VAD tuning, and gotchas discovered during integration.
