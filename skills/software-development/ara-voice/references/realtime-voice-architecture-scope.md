# Real-Time Voice Conversational Layer — Architecture Scope

**Date:** July 1, 2026
**Status:** Scoped, not built. Greg's directive: "Don't build anything — thought and scoping."

## The Goal

A bidirectional real-time voice conversation layer for ARA. Two use cases:
1. **Customers call a business WhatsApp number** → AI voice agent answers → live conversation with CRM context (order status, sales, support)
2. **Field sales reps call Ava** → coaching conversation with full CRM access

Greg's words: "A fully conversational layer" with live streaming STT → inference → TTS over WebSocket.

## The Stack (Researched & Validated)

### WhatsApp Business Calling API
- **Launched:** July 15, 2025 (Meta official, not a hack like Baileys)
- **Technology:** WebRTC (ICE + DTLS + SRTP), audio codec OPUS
- **Model:** "Bring your own VoIP" — Meta handles the WhatsApp user leg, business provides a WebRTC endpoint
- **Signaling:** Graph API webhooks (call connect/disconnect/status events)
- **Requirements:** Cloud API access, ≥2,000 daily messaging limit, `calls` permission, business verification
- **India:** Priority rollout market
- **Pricing:** Per-call + per-minute, varies by country
- **Docs:** https://developers.facebook.com/documentation/business-messaging/whatsapp/calling
- **Integration guide:** https://webrtc.ventures/2025/11/how-to-integrate-the-whatsapp-business-calling-api-with-webrtc-to-enable-customer-voice-calls

### Pipecat — The Integration Bridge
- **What:** Open-source Python framework for real-time voice AI agents
- **Why:** Has native `WhatsAppTransport` that handles the ENTIRE WhatsApp → WebRTC → AI pipeline lifecycle. Webhook processing, SDP negotiation, call lifecycle, audio streaming — all handled.
- **Repo:** https://github.com/pipecat-ai/pipecat (10K+ commits, 267+ contributors)
- **Install:** `uv add "pipecat-ai[webrtc]"`
- **WhatsAppTransport docs:** https://docs.pipecat.ai/api-reference/server/services/transport/whatsapp
- **Key API:**
  ```python
  from pipecat.transports.whatsapp import WhatsAppTransport
  
  async def handle_call(connection, call):
      caller_phone = call.From  # Phone number for CRM lookup
      call_id = call.id
      # Spawn bot with the WebRTC connection
  
  transport = WhatsAppTransport(
      whatsapp_token=WHATSAPP_TOKEN,
      phone_number_id=PHONE_NUMBER_ID,
      connection_callback=handle_call,
  )
  ```
- **Caller identification:** `call.From` gives the caller's phone number — direct CRM integration
- **WebRTC:** Uses `SmallWebRTCTransport` (serverless WebRTC via Python `aiortc`) per call

### Streaming STT — Deepgram
- Real-time streaming with ~300ms latency
- Nova-3 model, Hindi support (beta), Indian English
- ~$0.006-0.008/min (pay-as-you-go)
- Built-in VAD (Voice Activity Detection) for turn-taking
- Competing option: ElevenLabs Scribe v2 Realtime (~150ms, 30 languages, already in ARA for async)

### LLM — DeepSeek v4 (Already in ARA)
- Already the main model. Must use streaming token output for voice latency.
- Key difference from text: response latency matters more than response length. The LLM should emit short, conversational turns, not paragraphs.

### Streaming TTS — ElevenLabs
- **India-focused enterprise platform:** https://elevenlabs.io/india
- Indian English + Hindi voices, data residency, telephony integration
- Already have Scribe v2 in ARA for async STT (same vendor = simpler billing)
- Streaming TTS with low first-byte latency

### Alternatives Considered
| Component | Primary | Alternative |
|-----------|---------|-------------|
| Voice framework | Pipecat | LiveKit Agents |
| STT | Deepgram | ElevenLabs Scribe v2 Realtime |
| LLM | DeepSeek v4 | Groq (faster tokens), GPT-4o Realtime |
| TTS | ElevenLabs | Cartesia, Deepgram TTS, Azure Speech |
| WebRTC | Pipecat SmallWebRTC | Manual aiortc, LiveKit |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   THE VOICE LAYER                        │
│                                                         │
│  WhatsApp User calls business number                     │
│       │                                                 │
│       ▼                                                 │
│  Meta WhatsApp Cloud API                                │
│  (WebRTC: OPUS audio, ICE/DTLS/SRTP)                    │
│       │                                                 │
│       ▼  Webhook (call_id + SDP offer)                  │
│  ┌─────────────────────────────────────────┐            │
│  │        Pipecat WhatsAppTransport         │            │
│  │  • Handles WebRTC handshake              │            │
│  │  • Manages call lifecycle                │            │
│  │  • Extracts caller phone number          │            │
│  │  • Routes audio to/from AI pipeline      │            │
│  └──────────────┬──────────────────────────┘            │
│                 │                                        │
│                 ▼  Audio stream (16kHz, mono)            │
│  ┌─────────────────────────────────────────┐            │
│  │         Voice AI Pipeline               │            │
│  │                                         │            │
│  │  VAD (Silero) → STT (Deepgram)          │            │
│  │       │                                 │            │
│  │       ▼  Transcript text                │            │
│  │  ┌──────────────────────┐               │            │
│  │  │   CRM Context Inject  │               │            │
│  │  │  Phone → lead lookup  │               │            │
│  │  │  Order status,        │               │            │
│  │  │  Pipeline state,      │               │            │
│  │  │  Conversation history │               │            │
│  │  └──────────┬───────────┘               │            │
│  │             ▼                            │            │
│  │  LLM (DeepSeek v4) — streaming tokens   │            │
│  │  + Tool calling (CRM updates)            │            │
│  │       │                                 │            │
│  │       ▼  Response text                   │            │
│  │  TTS (ElevenLabs) — streaming audio     │            │
│  │       │                                 │            │
│  │       ▼  Audio stream back to caller     │            │
│  └─────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

## What Needs to Be Built

1. **WhatsApp Business API onboarding** — Cloud API access, phone number verification, calling permissions, webhook configuration (~1-2 weeks of process, not engineering)

2. **Pipecat voice agent** — the Python bot connecting STT → LLM → TTS (~2-3 days engineering — `WhatsAppTransport` does the heavy lifting)

3. **CRM context injection layer** — phone → lead/user lookup → context prompt. Key decision: how much CRM state per turn (~1-2 days)

4. **Conversational prompt design** — CRITICAL, highest-leverage. Voice conversations are different from text:
   - Barge-in/interruption handling (user talks over AI)
   - Turn-taking signals (pauses, filler words)
   - Graceful STT error handling ("I didn't catch that order number — could you repeat it?")
   - Escalation paths ("Let me transfer you to a human agent")
   - Voice-appropriate responses (short, conversational — not paragraphs)

5. **Tool calling during voice** — same schema as agent_chat but responses must be voice-appropriate. No `[TOOL_CALL:]` markers. No confirmation gates (voice is real-time). Things like "I found your order — it shipped yesterday and arrives Thursday."

6. **Post-call processing** — full transcript → CRM logging → action items → WhatsApp summary

## Two Use Cases

| | Customer Calls | Field Rep Calls |
|---|---|---|
| **Who** | Identifiable customer with phone in CRM | Greg or field rep |
| **Context** | Order status, account queries, sales, support | Meeting prep, lead coaching, CRM tasks |
| **Persona** | Professional, branded, on-script | Coaching partner (Ava persona) |
| **CRM Access** | Read-only customer data, limited tools | Full CRM tool access |
| **Example** | "Where is my order #4721?" | "What meetings do I have today?" |

## Rough Cost Model (Per-Minute)

| Component | Cost |
|-----------|------|
| WhatsApp Calling API | Per-call + per-minute (Meta pricing) |
| Deepgram STT (streaming) | ~$0.006-0.008/min |
| DeepSeek LLM | Existing + streaming token overhead |
| ElevenLabs TTS (streaming) | ~$0.015-0.03/min (est. for Indian voices) |
| Pipecat (self-hosted) | Free (open source) |
| Compute (Hetzner CX23) | ~€10-20/month |

**Total: roughly $0.02-0.05/min voice conversation** + WhatsApp per-minute charges.

## Key Design Decisions (To Be Made)

1. **Managed vs. self-hosted Pipecat?** Pipecat Cloud offers managed deployment. Self-hosted on Hetzner is cheaper but more ops.

2. **ElevenLabs Scribe v2 Realtime vs. Deepgram for STT?** Scribe v2 is already in ARA (async). Realtime variant claims 150ms latency. Could simplify to single vendor.

3. **OpenAI Realtime API as alternative?** Would replace Deepgram + DeepSeek + ElevenLabs with a single voice-to-voice API. $0.06/min input + $0.24/min output. Simpler but more expensive and less control over Indian language quality.

4. **Confirmation model for voice?** Text chat uses `[ACTION: ASK]` / `[ACTION: NOW]` gates. Voice can't pause for confirmation — different model needed. Options: (a) execute safe operations immediately, ask for risky ones, (b) post-call confirmation for data-modifying actions, (c) voice-specific "I'm about to update your order — shall I proceed?" with yes/no detection.

5. **Call recording?** WhatsApp Cloud API may support call recording. Transcripts are more valuable than raw audio for CRM logging.

## Research Gaps (Still to Validate)

- WhatsApp Calling API exact pricing for India
- Deepgram Hindi accuracy on real Indian call-center audio (noisy, accented)
- ElevenLabs TTS Indian English voice quality and latency
- Pipecat WhatsAppTransport concurrency limits (how many simultaneous calls on a Hetzner CX23?)
- Best approach for barge-in/interruption in the Pipecat pipeline
- Post-call transcript → agent_chat integration (reuse the voice-note routing or build new?)
