# WhatsApp Business Calling API — Condensed Research

**Status**: Live since July 15, 2025. Production-ready.

## Key Facts

- **Architecture**: "Bring Your Own VoIP" — Meta handles WhatsApp user leg, you provide WebRTC endpoint
- **Signaling**: Graph API + Webhooks (HTTPS)
- **Media**: WebRTC (ICE + DTLS + SRTP), OPUS codec (G.711 PCMA/PCMU added Mar 2026)
- **Inbound calls**: FREE. All Cloud API countries.
- **Outbound calls**: Billed per 6s. EXCLUDES USA, Canada, Egypt, Vietnam, Nigeria. Heavily rate-limited early.
- **Concurrent**: 1,000 calls/WABA
- **India**: Priority rollout market

## Setup Flow (Concrete, from 2026-07-04 deployment)\n\n### 1. Meta Developer Console\n\n- WABA ID: `122097552081389262` (name: \"Employee\")\n- Phone Number ID: `1230214920168618` (display: \"Arivu\", number: +91 73060 93959)\n- Phone verified, platform: CLOUD_API, quality: UNKNOWN\n- Webhook URL: `https://<tunnel>/whatsapp/webhook`\n- Verify token: `ara_whatsapp_voice_verify_2026`\n- Subscribed to `calls` webhook field\n\n### 2. Graph API endpoints that WORK (token-dependent)\n\n```bash\n# Verify token works — returns WABA name + ID\ncurl -s \"https://graph.facebook.com/v21.0/me?access_token=$TOKEN\"\n# → {\"name\":\"Employee\",\"id\":\"122097552081389262\"}\n\n# Get phone number details\ncurl -s \"https://graph.facebook.com/v21.0/1230214920168618?access_token=$TOKEN\"\n# → {\"verified_name\":\"Arivu\",\"display_phone_number\":\"+91 73060 93959\",...}\n```\n\n### 3. Graph API endpoints that DO NOT WORK (pre-Business-Verification)\n\n```bash\n# Subscribe app to WABA webhook — returns GraphMethodException error 100\nPOST /v21.0/{waba_id}/subscribed_apps\n# → \"Object does not exist, cannot be loaded due to missing permissions\"\n\n# Phone number fields that don't exist in v21.0\n?fields=phone_numbers        # → \"nonexisting field\"\n?fields=calls_configuration  # → \"nonexisting field\"\n?fields=connected_phone_numbers  # → \"nonexisting field\"\n```\n\n### 4. Webhook configuration is MANUAL until Business Verification\n\nGo to Meta Developer Console → WhatsApp → Configuration → Callback URL.\nSet the URL and verify token manually. Meta pings the GET endpoint immediately\n— `hub.mode=subscribe`, `hub.challenge=<number>`, `hub.verify_token=<your_token>`.\nServer must return the challenge value as plain text. Meta IP: `2a03:2880:2aff:68::`.\n\n### 5. Calling is automatically available\n\nNo separate \"enable calling\" toggle in the console for Cloud API numbers with\nverified code and webhook subscribed to `calls`. Incoming calls trigger\nwebhook POSTs automatically.

## Call Flow

1. WhatsApp user taps call button on business profile
2. Meta sends POST webhook with `event: connect`, `call_id`, SDP offer
3. Your server answers with SDP answer via Graph API
4. Full-duplex SRTP audio flows bidirectionally
5. You pipe audio frames to STT and back from TTS

## Baileys vs Calling API

| | Baileys | Calling API |
|---|---|---|
| Voice calls | ❌ No call signaling | ✅ Live voice |
| Media | Async .ogg voice notes | Real-time WebRTC SRTP |
| Protocol | Unofficial WebSocket | Official Graph API + WebRTC |
| Number | Any WhatsApp number | Cloud API number only |
| Can extend to voice | No | N/A (this IS voice) |

**Bottom line**: Baileys and Calling API run in PARALLEL on DIFFERENT numbers. Baileys for text/voice-notes, Calling API for live voice calls.

## Pipecat WhatsAppClient Pattern

Pipecat 1.4.0 has `WhatsAppClient` (not a standalone `WhatsAppTransport`). Usage:

```python
from pipecat.transports.whatsapp.client import WhatsAppClient

client = WhatsAppClient(
    whatsapp_token=TOKEN,
    phone_number_id=PHONE_ID,
    session=aiohttp.ClientSession(),
    whatsapp_secret=SECRET,  # optional
)

# In webhook handler:
await client.handle_webhook_request(
    request=webhook,
    connection_callback=on_call,  # async fn(connection, call)
    raw_body=raw_body,
    sha256_signature=sha256_sig,
)
```

The Pipecat DevelopmentRunner does NOT support WhatsApp. Must use custom FastAPI server.
