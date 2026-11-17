---
name: ara-voice
description: ARA voice capabilities — async voice notes via Baileys and real-time voice calling via WhatsApp Calling API. Covers Whisper transcription, coaching-thread routing, Pipecat architecture, STT→LLM→TTS cascade, and voice confirmation patterns.
---

# ARA Voice Capabilities

This skill covers all voice-related functionality in ARA — both async voice notes (transcribed and processed through the coaching thread) and real-time voice calls (live WebRTC conversations).

## Two Voice Modes

| Mode | Transport | Use Case | Documentation |
|------|-----------|----------|---------------|
| **Async Voice Notes** | Baileys sidecar + HTTP | Record → send → transcribe → respond | See "Voice Note Pipeline" below |
| **Real-Time Voice Calls** | WhatsApp Calling API + Pipecat | Live bidirectional conversation | See "Voice Calling" below |

## Voice Note Pipeline

> **For async voice notes (record → send → transcribe → respond), see `ara-voice-pipeline`.** This skill absorbs that content for discoverability.

Voice notes are treated as **just another message format** — transcribed and fed into the coaching thread identically to text messages.

### Architecture

```
Voice note (WhatsApp self-chat)
  → Sidecar sendAudioToARA() → POST /api/whatsapp/voice-inbound
  → Scribe v2 transcription (ElevenLabs) with speaker diarization
  → Fallback: Whisper small.en
  → ROUTING:
      ├─ Transcript contains "eval"/"evaluate"? → EVAL PIPELINE
      ├─ Duration > 90s, no keyword? → AMBIGUITY ASK
      └─ Default → COACHING PIPELINE
```

### Key Design Decisions

1. **Single coaching thread** — Both text and voice go through the same thread for context awareness
2. **No field-agent wrapper** — Just `🎤 {transcript}`, plain text with source prefix
3. **No separate confirmation flow** — Voice notes use the same `[ACTION: ASK/NOW]` gates as text
4. **Contact detail guard** — Email/phone/name from voice notes require explicit confirmation due to STT garble risk

### Voice Confirmation Patterns

When voice notes propose data-modifying actions:

- **Layer 1:** System prompt rule — show values and ask before executing
- **Layer 2:** Code guard — `voice_note` flag forces `[ACTION: ASK]`
- **Layer 3:** `pre_confirmed` flag — bypasses gate when user explicitly confirms

See `references/voice-confirmation-debugging-june14-2026.md` for full implementation.

## Voice Calling

> **For real-time voice calls (live WebRTC via WhatsApp Calling API), see `ara-voice-calling`.** This skill absorbs that content for discoverability.

Real-time voice uses Pipecat with:
- **STT:** ElevenLabs Scribe v2 Realtime (or Deepgram streaming)
- **LLM:** DeepSeek V4 Pro (default) or configurable
- **TTS:** ElevenLabs (streaming)
- **Transport:** SmallWebRTSTransport or WhatsApp Calling API

### Architecture

```
User's phone (WhatsApp call)
  → Meta Cloud API (WhatsApp Calling)
  → Pipecat pipeline:
       STT → LLM → TTS
  → User hears response
```

### Voice Confirmation in Calls

- **Dual confirm safety:** Proposes actions, asks for verbal confirmation before executing
- **Batch confirmation:** Stage all actions silently, present as batch, confirm with one "confirm"
- **Immediate notification:** After confirmation, sends WhatsApp summary to owner

### Pipecat Patterns

See `references/narrationgate-bridge-patterns-july2026.md` for:
- NarrationGate — suppress LLM thinking/narration from TTS
- TTSSanitizer — strip markdown before TTS
- FrameProcessor passthrough requirements

## Common Patterns

### Voice-Text Parity

Voice and text should behave identically:
- Same confirmation gates
- Same thread context
- Same tool execution
- Same fallback logic

### STT Provider Selection

| Provider | Use Case | Cost |
|----------|----------|------|
| ElevenLabs Scribe v2 | Primary, best accuracy | Pay per second |
| Whisper (local) | Fallback when API fails | Free (compute) |
| Deepgram Streaming | Real-time calls | Pay per second |

### Error Handling

Every exit path must produce user-facing output:
- Empty transcript → "Sorry, I could not understand the audio..."
- 5xx error → "Sorry, I ran into an error processing that..."
- Timeout → "Could you send a text message instead?"

## References

### From ara-voice-pipeline
- `references/scribe-v2-integration.md` — Scribe v2 STT setup
- `references/voice-confirmation-debugging-june14-2026.md` — Full confirmation trace
- `references/voice-routing-design-june25.md` — Routing logic
- `references/tts-sanitizer-july2026.md` — Markdown stripping

### From ara-voice-calling
- `references/ara-voice-phase1-tool-calling.md` — Tool calling in voice
- `references/voice-confirm-audit-design.md` — Confirmation UX
- `references/vad-mandatory-for-stt.md` — VAD requirements
- `references/elevenlabs-tts-auth-issue.md` — Auth troubleshooting

## Pitfalls

### Voice Prefix Detection
Voice notes enter with `🎤` prefix. Question detection must strip this before checking:
```python
_msg_clean = user_msg.lstrip('🎤').strip()
```

### data_modifying_tools Sync
Every new mutation tool MUST be added to `data_modifying_tools` set or voice gate won't fire.

### Pre-Confirmed Order
`pre_confirmed` check MUST run BEFORE `voice_note` check — voice notes always win.

### Interim Messaging
Send "Processing..." BEFORE audio transcription starts — user needs feedback during 10-25s latency.

### NarrationGate Required
Without it, LLM thinking ("Let me check that...") leaks into TTS and is read aloud to user.
