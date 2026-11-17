# ARA Voice Layer — Final Validated Plan of Action
# July 1, 2026 — Senior architecture review (TA validated)

## Inference Strategy (Final)

| Role | Model | Why |
|------|-------|-----|
| **Default voice** | Groq / Llama 4 Scout | <100ms TTFT, $0.20/1M, 460+ t/s |
| **Fallback voice** | GPT-5.4 mini | Stronger tool calling (OpenAI), 740ms TTFT — accept latency penalty |
| **Text only** | DeepSeek V3.2 | Reasoning depth for CRM ops, 820ms+ TTFT disqualifies from voice |

GPT-5.4 mini: "2x faster" is throughput, NOT TTFT. Actual measured TTFT: 740ms (reasoning mode), ~1.2s (non-reasoning). 7-8x slower than Groq for voice. Include in bake-off as tool-accuracy benchmark, not as default.

## Safety Gaps Found (beyond initial plan)

1. **Spoken data exfiltration via mishearing**: Fix with ANI scope-locking — voice agent can ONLY read data for the authenticated caller's phone number.
2. **Voice→text handoff untested**: Fix with draft-and-link pattern. Voice creates DRAFT (not committed), WhatsApp message with confirm/reject buttons, only button-tap commits. Drafts expire in 10 minutes.
3. **No voice audit trail**: Fix with mandatory transcript logging. Both STT sides + agent actions → CRM logs.

## Phase 0 — Empirical Gates (DO NOT SKIP)

| Gate | What | Pass Criterion |
|------|------|----------------|
| 0.1 | Latency from India | Groq end-to-end <700ms P50 |
| 0.2 | Tool-calling bake-off | ≥95% correct tool calls on ARA CRM schema (GO/NO-GO) |
| 0.3 | Hindi TTS + STT quality | STT WER <15% code-switching, TTS ≥4/5 naturalness |
| 0.4 | WhatsApp API access | Inbound call → webhook → SDP exchange works |

Gate 0.2 is the go/no-go. If no model hits 95% tool accuracy on ARA's CRM schema, voice-read V1 is not safe.

## Decision Matrix

| Decision | Recommendation | Confidence |
|----------|---------------|------------|
| Cascade vs S2S | Cascade (settled) | High |
| Default voice LLM | Groq/Llama 4 Scout | High (latency) / Medium (tool accuracy pending Gate 0.2) |
| GPT-5.4 mini | Bake-off only, not default | High |
| DeepSeek for voice | No — text only | High |
| V1 scope | Voice-read only, customer-facing | High |
| V2 scope | Voice-read + text-confirm writes (draft-and-link) | High |
| Hind TTS | A/B test ElevenLabs vs Sarvam AI | High |

Note: Greg chose GPT 5.4 mini for initial testing despite latency data — his empirical call.
