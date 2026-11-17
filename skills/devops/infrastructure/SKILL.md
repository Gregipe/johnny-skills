---
name: infrastructure
description: Infrastructure and platform setup — gateways, webhooks, voice agents, and system services
---

# Infrastructure

This skill covers infrastructure and platform setup skills. Use the appropriate section for your task.

## Gateway Platform Setup

**When to use:** Adding a messaging platform (Discord, Telegram, Slack) to Hermes gateway

### Platform Checklist

For every platform, you need:
| What | Where | Example |
|------|-------|---------|
| Bot token/credential | Profile `.env` | `DISCORD_BOT_TOKEN=xxx` |
| Allowed users | Profile `.env` | `DISCORD_ALLOWED_USERS=user_id1,user_id2` |
| Enabled flag | Profile `config.yaml` | `discord.enabled: true` |
| Channel prompts | Profile `config.yaml` | Per-channel system prompts |
| Home channel | Profile `.env` | Cron delivery target |

---

## Webhook Subscriptions

**When to use:** Setting up event-driven agent runs via webhooks

**Workflow:**
- Define webhook event types
- Configure webhook endpoint
- Set up authentication
- Register subscriptions

---

## Pipecat Voice Agent

**When to use:** Building real-time voice agents with Pipecat 1.4.0

**Prerequisites:**
- Pipecat 1.4.0+ installed (`pipecat-ai[webrtc]`)
- ElevenLabs API key (for STT or TTS)
- OpenAI API key (for LLM or STT)
- Python 3.11+
- TURN server for production

**Canonical Pipeline:** Uses `WorkerRunner` + `PipelineWorker` (NOT deprecated `PipelineRunner`)

---

## macOS Launchd Service

**When to use:** Auto-starting services on macOS

**Workflow:**
- Create LaunchAgent plist at `~/Library/LaunchAgents/<name>.plist`
- Configure PATH/environment
- Use `launchctl load` / `launchctl unload` to manage
- Handle crash recovery with `KeepAlive`

---

## Related Skills

- `ara-devops` — ARA-specific DevOps workflows
- `ara-production-deploy` — Deploy to production
- `whatsapp-integration` — WhatsApp messaging