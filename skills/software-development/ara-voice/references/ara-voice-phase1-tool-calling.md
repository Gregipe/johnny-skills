# ARA Voice Tool Calling — Phase 1 Implementation

## Architecture

Pipecat (`:8768`) and ARA (`:8766`) run as separate processes on Hetzner. Voice agent calls ARA via HTTP using `X-Voice-Secret` for server-to-server auth.

## ARA Endpoints

All endpoints are in `/opt/ara/server.py`:

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/voice/session` | POST | Dashboard session (same-origin) | Mint single-use voice token |
| `/api/voice/session/verify` | POST | `X-Voice-Secret` | Consume token, return `tenant_id` |
| `/api/voice/tools` | GET | `?secret=` query param | Return read-only tool schemas |
| `/api/voice/tool` | POST | `{"secret": "..."}` in body | Execute a read-only tool |

### Token Lifecycle
1. Browser JS calls `/api/voice/session` (same-origin, no auth needed) → gets `{voice_token}`
2. Intended: Browser passes `voice_token` in Pipecat `/start` body → Pipecat stores in `active_sessions`
3. **BROKEN**: Pipecat's `runner_args.body` = WebRTC SDP, NOT `/start` POST body. Token lost.
4. **Phase 1 workaround**: Pipecat uses `ARA_VOICE_SECRET` directly + hardcoded `tenant_id`.

### Read-Only Whitelist

`VOICE_SAFE_TOOLS` — read-only tool names: `search_leads`, `query_leads`, `get_lead_detail`, `get_pipeline_summary`, `get_summary`, `get_action_items`, `get_activity_log`, `search_knowledge_base`.

Dual check: tool must be in `VOICE_SAFE_TOOLS` AND `TOOL_SCHEMAS[tool]["read_only"] is True`.

### Security Rules
1. `X-Voice-Secret` is server-to-server only (localhost `:8768` ↔ `:8766`)
2. Never appears in browser-visible code (dashboard HTML, JS, templates)
3. Token is single-use, 60s TTL, consumed on first `verify` call

## Pipecat Tool Calling Pattern

`/opt/ara-voice-agent/voice_tools.py`:
- Fetches tool schemas from `GET /api/voice/tools?secret=`
- Builds `FunctionSchema(name, description, properties, required, handler=...)`
- Handler: reads `tenant_id` + `http_client` from `params.app_resources`, POSTs to `/api/voice/tool`, calls `await params.result_callback(result)`
- Catches `ConnectError` + `TimeoutException` → spoken fallback messages

Bot injection:
- `LLMContext(tools=voice_tools)` in `build_pipeline()`
- `PipelineWorker(app_resources={"tenant_id": ..., "http_client": http})`
- `httpx.AsyncClient` wraps entire session (`async with` in `bot()`)

## System Prompt

```
You are Ava, an AI voice assistant for the user's CRM dashboard.
Spoken-style output: 1-2 sentences, no markdown, no bullet lists.
Use tools for any data question - never fabricate.
Summarize results naturally.
If asked to create/update/send: "I can't make changes by voice yet - I can look anything up for you."
```

## Gate Tests

All passing as of July 3, 2026:

- T1: Secret never in dashboard HTML ✅
- T2: Single-use token, reuse gets 401 ✅
- T3: Read tool executes, write tool rejected ✅
- T4: Tenant returned from verify ✅
- T7: ConnectError + TimeoutException caught in voice_tools.py ✅
- T8: Existing ARA endpoints still work ✅

Manual: T5 (E2E browser voice) + T6 (Orb/UI states)

## Files

| File | Location | Purpose |
|------|----------|---------|
| `server.py` | `/opt/ara/server.py` | ARA endpoints + VOICE_SAFE_TOOLS |
| `bot.py` | `/opt/ara-voice-agent/bot.py` | Pipecat runner, pipeline, tool injection |
| `voice_tools.py` | `/opt/ara-voice-agent/voice_tools.py` | ARA tool schema fetch + FunctionSchema build |
| `dashboard_template.py` | `/opt/ara/dashboard_template.py` | Voice overlay HTML/CSS/JS |
| `DESIGN_TOOL_CALLING.md` | `/Users/greg/ara-voice-agent/` | Full design doc |
| `TA_IMPLEMENTATION_BRIEF.md` | `/Users/greg/ara-voice-agent/` | TA brief with verified Pipecat APIs |
