# WhatsApp Voice Agent Reference

## Server State (as of 2026-07-04)

All servers on Hetzner (46.224.132.99) under `/opt/ara-voice-agent/`:

| File | Port | Purpose |
|------|------|---------|
| `bot.py` | 7860 | Dashboard voice agent (browser WebRTC) |
| `whatsapp_server.py` | 8780 | WhatsApp Cloud API webhook + call handler |
| `whatsapp_proxy.py` | 8781 | Path-based reverse proxy for ngrok |
| `.env` | — | Shared env vars (both bots read from same file) |

## Ngrok

Single ngrok process mapping 8781 to `supportlessly-fourcha-inez.ngrok-free.dev`

## WhatsApp Business Account

- WABA ID: 122097552081389262
- Business name: Employee
- Phone number: +91 73060 93959 (ID: 1230214920168618)
- Display name: Arivu
- Platform: CLOUD_API
- Status: VERIFIED

## Logs

| Service | Log Path |
|---------|----------|
| Voice agent | /var/log/ara-voice.log |
| WhatsApp | /var/log/whatsapp-voice.log |
| Proxy | /var/log/proxy.log |
| Ngrok | /var/log/ngrok-wa.log |
