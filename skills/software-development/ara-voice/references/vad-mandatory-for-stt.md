# TA Analysis: VAD + Context Aggregation Root Cause (July 3, 2026)

## Summary
The ARA voice agent was silent despite WebRTC connecting, all services initializing, and STT producing transcriptions. Root cause: bare `VADProcessor` emits speech-boundary frames but the STT's `TranscriptionFrame` is never converted to `LLMMessagesFrame` that the LLM can process. The fix is `LLMContextAggregatorPair`.

## Diagnostic Timeline

### Phase 1: TransportParams defaults
- `audio_in_enabled` defaults to `False` — fixed
- `audio_out_enabled` defaults to `False` — fixed
- `audio_in_passthrough` defaults to `True` (confirmed `base_transport.py:79`) — NOT the problem, but was suspected

### Phase 2: Deprecated Runner
- `PipelineRunner` deprecated since 1.3.0 — switched to `PipelineWorker` + `WorkerRunner`
- Fixed pipeline services never starting

### Phase 3: TURN Server
- WebRTC media over UDP blocked behind NAT
- Installed coturn on Hetzner, patched runner ICE config
- TURN relay candidates appeared, sessions stabilized

### Phase 4: VAD Discovery
- TA analyzed Pipecat 1.4.0 source
- `ElevenLabsRealtimeSTTService` (extends `WebsocketSTTService`) needs VAD stop frames to send commit message (`elevenlabs/stt.py:685-693`)
- Added `VADProcessor(SileroVADAnalyzer())` — VAD frames fired, STT produced committed transcripts

### Phase 5: The Final Gap
- STT produced transcription ("Hi, there", "Can you hear me?", etc.) — confirmed in logs
- But LLM NEVER responded — no API calls, no output
- `TranscriptionFrame` is pushed downstream by STT but `OpenAILLMService` doesn't handle it
- `TranscriptionFrame` needs to be converted to `LLMMessagesFrame` by a user context aggregator

## Root Cause

The Pipecat cascade template uses `LLMContextAggregatorPair` (from `pipecat.processors.aggregators.llm_response_universal`) which provides:
1. **`user_aggregator`**: VAD (via `SileroVADAnalyzer` in `LLMUserAggregatorParams`) + conversion of `TranscriptionFrame` → `LLMMessagesFrame`
2. **`assistant_aggregator`**: captures assistant responses and adds them to LLM context

The pipeline in the Pipecat template (`pipeline_components.jinja2` lines 56-67):
```python
pipeline = Pipeline([
    transport.input(),      # input_stage
    stt,                    # stt_stage
    user_aggregator,        # context_user_stage ← MISSING FROM OUR BOT
    llm,                    # llm_stage
    tts,                    # tts_stage
    transport.output(),     # output_stage
    assistant_aggregator,   # context_assistant_stage
])
```

## Fix Applied

```python
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.aggregators.llm_context import LLMContext

context = LLMContext()
user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
    context,
    user_params=LLMUserAggregatorParams(
        vad_analyzer=SileroVADAnalyzer(),
    ),
)
```

## Source Files Referenced
- `pipecat/processors/aggregators/llm_response_universal.py:2090` — `LLMContextAggregatorPair`
- `pipecat/services/elevenlabs/stt.py:685-693` — commit message on VAD stop
- `pipecat/services/elevenlabs/stt.py:968` — `_on_committed_transcript` pushes `TranscriptionFrame`
- `pipecat/cli/templates/server/_macros/pipeline_components.jinja2:17-18` — `context_user_stage` macro
- `pipecat/cli/templates/server/_macros/helper_functions.jinja2` — `setup_context` creates the pair
- `pipecat/transports/base_input.py:284` — `audio_in_passthrough` gate (defaults True)
- `pipecat/transports/base_transport.py:79` — `audio_in_passthrough: bool = True`

## Verification
1. Logs MUST show: `VADUserStartedSpeakingFrame` → `VADUserStoppedSpeakingFrame` → committed transcript → LLM response → TTS audio
2. If VAD fires and STT transcribes but LLM doesn't respond: missing user_aggregator
3. If nothing fires: check `audio_in_enabled=True`, `audio_out_enabled=True`, TURN server, STT credentials
