# ARA Voice Agent Latency Audit (July 4, 2026)

Comprehensive latency analysis of the ARA voice pipeline at /opt/ara-voice-agent/bot.py (Pipecat 1.4.0, Python 3.11.15, Hetzner 46.224.132.99).

## Pipeline Stages (current timing)

| # | Stage | Time | Target |
|---|-------|------|--------|
| 1 | WebRTC ICE + connection | ~800ms | ~300ms |
| 2 | STT WebSocket connect | ~170ms | ~170ms ✓ |
| 3 | TTS WebSocket connect | ~45ms | ~45ms ✓ |
| 4 | VAD start_secs debounce | 600ms | 200ms |
| 5 | VAD stop_secs debounce | 300ms | 200ms |
| 6 | Smart Turn v3 ONNX analysis | 2-8s | 0ms (remove) |
| 7 | user_turn_stop_timeout fallback | 2.0s | 0.6s |
| 8 | STT p99 transcript wait | 0.41s | 0.41s |
| 9 | LLM TTFT (gpt-5.4-mini) | 1-3s | 0.5s |
| 10 | TTS first audio byte | 200-400ms | 200ms |
| **Total** | | **~10-20s** | **~2.5-4s** |

## Prioritized Optimizations

### P1: VAD-only turn start + SpeechTimeout stop (saves 4-10s)
Replace default turn strategies that include `TranscriptionUserTurnStartStrategy` (fires on STT output including echo) with `VADUserTurnStartStrategy` only. Replace Smart Turn v3 with `SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=0.6)`.

```python
from pipecat.turns.user_start import VADUserTurnStartStrategy
from pipecat.turns.user_stop import SpeechTimeoutUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies

user_params=LLMUserAggregatorParams(
    vad_analyzer=SileroVADAnalyzer(params=VADParams(confidence=0.7, start_secs=0.2, stop_secs=0.2, min_volume=0.6)),
    user_turn_stop_timeout=1.0,
    user_turn_strategies=UserTurnStrategies(
        start=[VADUserTurnStartStrategy()],
        stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=0.6, wait_for_transcript=True)],
    ),
)
```

### P2: Tighten VAD params (saves 500ms)
start_secs: 0.6 → 0.2, stop_secs: 0.3 → 0.2, min_volume: 0.65 → 0.6

### P3: STT VAD commit strategy (saves 300-500ms)
Switch from `CommitStrategy.MANUAL` to `CommitStrategy.VAD`. Medium risk — ElevenLabs controls commit timing.

### P4: Reduce stop timeout to 1.0s (saves 1.0s)
Safety net only — `SpeechTimeoutUserTurnStopStrategy` fires first.

### P5: LLM optimization (saves 0.5-2.5s)
Set `LLM_MODEL` explicitly, reduce tools, temperature=0.3, max_completion_tokens=100.

### P6: TTS voice settings (saves 100-300ms)
speed=1.1, stability=0.5, similarity_boost=0.75

## Environment Discrepancies Found
- Python is 3.11.15 (not 3.14.4 as documented)
- LLM_MODEL is not set in .env (defaults to gpt-5.4-mini, not DeepSeek V4)
- bot-sessions.log is 0 bytes (permission issue — root-owned file, process runs as different user)
