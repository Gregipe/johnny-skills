# Voice Architecture Decision — Cascade vs Speech-to-Speech

## Decision: Cascade (STT → LLM → TTS)

Settled. Not up for debate. Reasoning:

| | Cascade | Speech-to-Speech |
|---|---|---|
| Tool calling | ✅ Standard function calling | ❌ Not reliable |
| CRM context injection | ✅ Prompt engineering | ❌ No prompt surface |
| Debuggability | ✅ Text at every stage | ❌ Audio-only |
| LLM flexibility | ✅ Swap via config | ❌ Retrain entire model |
| Production readiness | ✅ Dominant in production | ⚠️ Research/prototype |

ARA's entire value is in the text layer where tool calls, CRM context, and conversation logic live. S2S removes that layer.

## Inference Strategy

### Default: Groq / Llama 4 Scout
- TTFT: < 100ms server-side, ~250-350ms from India
- Cost: ~$0.20/1M blended (cheapest)
- Tool calling: 55.7% BFCL v3 — MUST verify on ARA CRM schema in Phase 0 bake-off
- Output: 460+ t/s — TTS never starves

### Fallback: GPT-5.4 mini
- TTFT: 740ms measured (NOT suitable for sub-700ms budget)
- Tool calling: Likely stronger than Llama (OpenAI function calling is mature)
- Cost: $0.75/$4.50 per 1M
- Use only if Groq fails tool-calling accuracy bake-off
- **The "2x faster" claim is about throughput, not TTFT.** TTFT is 7-8x slower than Groq.

### Text-only: DeepSeek V3.2
- TTFT: 820ms (DeepInfra), 1.9s (native API) — disqualified from voice
- Kept in text agent_chat where reasoning depth matters and latency doesn't

### Model-Agnostic Router
Config-driven, swap via `config.yaml`:
```yaml
voice:
  llm:
    provider: groq
    model: llama-4-scout
    fallback:
      provider: openai
      model: gpt-5.4-mini
text:
  llm:
    provider: deepinfra
    model: deepseek-v3.2
```

## STT: ElevenLabs Scribe v2 Realtime
- ~150ms latency, 90+ languages including Hindi
- India data residency
- Natural upgrade from current Scribe v2 (async)
- Alternative: Deepgram Nova-3 (~150ms, Hindi via multilingual, built-in turn detection)

## TTS: ElevenLabs Flash v2.5
- ~75ms first-byte latency
- Hindi via multilingual model
- Alternative: Sarvam AI (11 Indian languages, 35+ voices — worth A/B testing)
- Dealbreaker: Deepgram Aura-2 does NOT support Hindi

## Latency Budget
- Target: < 500ms (ideal), < 700ms (acceptable), > 1s (failure)
- ALL numbers are unmeasured from India. Phase 0 Gate 0.1 required.
- Groq path: STT 150ms + LLM 250-350ms + TTS 75ms + network 150ms = ~625-725ms from India
