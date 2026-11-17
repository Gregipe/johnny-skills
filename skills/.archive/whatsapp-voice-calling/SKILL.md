---
name: whatsapp-voice-calling
description: WhatsApp Cloud API voice calling with Pipecat.
version: 1.0.0
author: Greg (via Johnny, Chief of Staff)
platforms: [linux]
metadata:
  hermes:
    tags: [whatsapp, voice, pipecat, webrtc, deployment]
    related_skills: [whatsapp-integration, pipecat-voice-agent]
---

# WhatsApp Voice Calling Skill

## When to Use
When setting up, debugging, or extending WhatsApp Cloud API voice calling — the official Meta API for real-time phone calls via WhatsApp, as opposed to text messaging (Baileys sidecar) or voice notes.

## Architecture

```
WhatsApp Call → Meta Cloud API webhook (:8780) → WhatsAppClient
  → SmallWebRTCConnection → spawns Pipecat pipeline:
      STT (ElevenLabs Scribe v2) → LLM (model-agnostic) → TTS (ElevenLabs)
```

Three servers run together:
| Port | Service | File |
|------|---------|------|
| 7860 | Dashboard voice agent (browser WebRTC) | `bot.py` |
| 8780 | WhatsApp webhook server | `whatsapp_server.py` |
| 8781 | Reverse proxy | `whatsapp_proxy.py` |

The proxy routes `/whatsapp/*` → 8780, everything else → 7860. This is needed because ngrok free tier gives 1 URL — both services share it via path-based routing.

## Prerequisites

- Meta Business Account with WhatsApp Cloud API access
- Phone number registered with `CLOUD_API` platform type
- Webhook callback URL configured in Meta Developer Console
- `calls` webhook field subscribed
- ElevenLabs API key (STT + TTS)
- LLM API key (DeepSeek or Groq)
- Pipecat 1.4.0+ with `SmallWebRTCTransport`

## Setup

### 1. Meta Developer Console

- **Webhook URL**: `https://<ngrok-domain>/whatsapp/webhook`
- **Verify token**: `ara_whatsapp_voice_verify_2026` (or any value you set in `.env` as `WHATSAPP_WEBHOOK_VERIFY_TOKEN`)
- **Subscribed fields**: `calls`

### 2. Environment (.env)

All keys live in `/opt/ara-voice-agent/.env`:

```
WHATSAPP_TOKEN=<permanent access token>
WHATSAPP_PHONE_NUMBER_ID=<from Meta Console>
WHATSAPP_WEBHOOK_VERIFY_TOKEN=<any string>
WHATSAPP_APP_SECRET=<optional — enables HMAC webhook validation>

WHATSAPP_LLM_PROVIDER=deepseek
WHATSAPP_LLM_MODEL=deepseek-chat
WHATSAPP_LLM_API_KEY=<api key>
WHATSAPP_LLM_BASE_URL=https://api.deepseek.com/v1
WHATSAPP_LLM_TEMPERATURE=0.3

ELEVENLABS_API_KEY=<key>
STT_MODEL=scribe_v2_realtime
TTS_VOICE_ID=XrExE9yKIg1WjnnlVkGX
TTS_MODEL=eleven_turbo_v2_5

ARA_VOICE_SECRET=<optional>
ARA_TENANT_ID=3e736242
ARA_BASE_URL=http://localhost:8766
```

### 3. Ngrok + Proxy

Start ngrok pointing to port 8781 (the proxy):
```bash
ngrok http 8781 --log=stdout > /var/log/ngrok-wa.log 2>&1 &
```

## Model Router

The LLM is config-driven — swap models by changing `.env`:

```bash
# DeepSeek (default — ~1.9s TTFT)
WHATSAPP_LLM_PROVIDER=deepseek
WHATSAPP_LLM_MODEL=deepseek-chat
WHATSAPP_LLM_BASE_URL=https://api.deepseek.com/v1

# Groq (fastest — ~200ms TTFT, needs separate API key)
WHATSAPP_LLM_PROVIDER=groq
WHATSAPP_LLM_MODEL=llama-3.3-70b-versatile
WHATSAPP_LLM_API_KEY=<groq key>

# DeepInfra (DeepSeek with lower latency)
WHATSAPP_LLM_PROVIDER=deepinfra
WHATSAPP_LLM_MODEL=deepseek-ai/DeepSeek-V3.2
WHATSAPP_LLM_BASE_URL=https://api.deepinfra.com/v1/openai
```

## CRM Context

The `whatsapp_bot.py` attempts to resolve the caller's phone number via:
```
POST /api/voice/context {secret, tenant_id, phone}
    → {name, role, actions[], pipeline, meetings}
```

If the endpoint doesn't exist (or fails), the bot falls back to a generic prompt — it still works but lacks personalization.

## Pitfalls

### .env overwrite kills the dashboard voice agent
The WhatsApp server and the dashboard voice agent (bot.py) share `/opt/ara-voice-agent/.env`. **Never replace the .env file — always append.** The dashboard agent needs `OPENAI_API_KEY` and `DEEPSEEK_API_KEY`. If you overwrite .env with only WhatsApp vars, bot.py crashes on next call with `OpenAIError: Missing credentials`.

### Port drift: bot.py changed from 8768 → 7860
The ARA server at `/opt/ara/server.py` has a hardcoded voice proxy to `localhost:8768`. If bot.py changes its listening port, update both:
1. `server.py` line ~12921 — the proxy URL
2. `whatsapp_proxy.py` — the VOICE_PORT default
3. Systemd or nohup launch command if it specifies a port

Check with: `grep -n "localhost:8768\|localhost:7860" /opt/ara/server.py`

### Ngrok free tier: 1 URL, many services
Free ngrok gives exactly 1 public URL. To expose multiple services (voice agent + WhatsApp webhook), use a path-based reverse proxy (`whatsapp_proxy.py`) that routes:
- `/whatsapp/*` → WhatsApp server (8780)
- `/*` → Voice agent (7860)

Start ngrok against the proxy port (8781), not any individual service port.

### WhatsApp calling not enabled by default
Even with webhook configured, calling may not work if the phone number isn't verified or calling isn't enabled. Check the phone number status via:
```bash
curl -s "https://graph.facebook.com/v21.0/{PHONE_ID}?access_token={TOKEN}"
```
The phone must show `platform_type: "CLOUD_API"` and `code_verification_status: "VERIFIED"`.

### `calls_configuration` field doesn't exist in v21.0
The Meta Graph API docs reference a `calls_configuration` field, but in v21.0 it returns `(#100) Tried accessing nonexisting field`. Calling capability is inferred from the phone being `CLOUD_API` type — there's no separate toggle endpoint in the current API version.
