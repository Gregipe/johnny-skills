# Browser Voice Integration — Dashboard Scope

Goal: Add ChatGPT-Voice-Mode-style conversational voice to ARA dashboard at ara.move78.work/dashboard, reusing the same Pipecat STT/LLM/TTS pipeline.

## Architecture

Browser React dashboard → WebRTC (SmallWebRTCTransport) → Pipecat runner (port 8768) → same STT/LLM/TTS pipeline as WhatsApp calls.

The runner (`bot.py --whatsapp --port 8768`) handles BOTH transports from one FastAPI process:
- `/start` — WebRTC signaling for browser
- `/api/offer` — SDP exchange  
- `/whatsapp` — WhatsApp webhook for phone calls

## React Integration

Use `@pipecat-ai/react-client` + `@pipecat-ai/voice-ui-kit`:
- `PipecatClientProvider` — wraps app with client instance
- `PipecatClientAudio` — mounts bot's return audio
- `PipecatClientMicToggle` — headless mic component
- `VoiceVisualizer` — animated audio waveform orb
- `usePipecatConversation()` — live transcripts

## Auth Flow

1. User logged into ARA dashboard → has ARA JWT/cookie
2. User clicks "Voice Mode" button
3. React calls `pcClient.startBotAndConnect({ endpoint: '/start', requestData: { ara_token, user_id } })`
4. Runner validates token via FastAPI dependency → passes `user_id` to `bot()` via `runner_args.body`
5. Bot uses `user_id` to personalize system prompt / fetch CRM context

Auth travels in the `/start` request body, not through the WebRTC connection itself.

## Build Phases

| Phase | What | Effort |
|-------|------|--------|
| 0 | Pipecat prebuilt `/client` UI — proves pipeline works | 4h (done) |
| 1 | Production server: TLS (nginx+certbot), TURN, ARA auth | 1 day |
| 2 | React component in dashboard | 1-2 days |
| 3 | Live transcripts, CRM context, persistence | 1-2 days |

**Total MVP: ~3 days**

## Critical Risks

- **No TURN server** → ~10-20% of users behind strict NATs can't connect
- **No HTTPS** → browsers block `getUserMedia` on HTTP
- **Concurrent sessions** → runner spawns subprocess per session, fine for <10 concurrent

## Getting the URL

The ngrok URL is persistent (`supportlessly-fourcha-inez.ngrok-free.dev`) while the paid account is active. For production, use `voice.ara.move78.work` with nginx + certbot.

Ref: /Users/greg/.hermes/hermes-agent/ARA_VOICE_INTERFACE_SCOPE.md (original TA scope document)
