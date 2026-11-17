# WhatsApp Calling — Pipecat Voice Agent Infrastructure

## Architecture

WhatsApp voice calls use **Meta's Cloud API** (official, not Baileys WebSocket). The integration is:

```
WhatsApp Caller → Meta Cloud API → webhook POST to your server → 
WhatsAppClient → SmallWebRTCConnection → SmallWebRTCTransport → 
STT → LLM → TTS → back to caller
```

`WhatsAppClient` handles signaling (webhooks, call lifecycle). Actual audio/WebRTC uses the same `SmallWebRTCTransport` as browser WebRTC — the WhatsApp module is the *signaling layer*, not a separate transport.

## Prerequisites

1. Meta Business Verification
2. WhatsApp Business API phone number (separate from Baileys/personal number)
3. Permanent access token from Meta Developer Console
4. Webhook URL accessible from the internet (ngrok or public IP)
5. Pipecat 1.4.0+ (`pipecat-ai[webrtc]`)

## FastAPI Webhook Server

The server handles two webhook routes:

```python
from pipecat.transports.whatsapp.client import WhatsAppClient
from pipecat.transports.whatsapp.api import WhatsAppWebhookRequest, WhatsAppConnectCall

app = FastAPI()

@app.get("/whatsapp/webhook")
async def webhook_verify(hub_mode, hub_challenge, hub_verify_token):
    """Meta sends this to verify the webhook URL. Must echo hub.challenge."""
    if hub_verify_token != WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse("Token mismatch", 403)
    return PlainTextResponse(hub_challenge)

@app.post("/whatsapp/webhook")
async def webhook_event(request: Request):
    """Meta sends POST for call lifecycle: connect, terminate."""
    raw_body = await request.body()
    payload = json.loads(raw_body)
    webhook = WhatsAppWebhookRequest(**payload)
    
    client = await _get_whatsapp_client()
    await client.handle_webhook_request(
        webhook,
        connection_callback=_on_whatsapp_call,  # calls spawn_whatsapp_bot()
        raw_body=raw_body,
        sha256_signature=request.headers.get("X-Hub-Signature-256", ""),
    )
    return {"status": "ok"}
```

## WhatsAppClient Setup

```python
import aiohttp
from pipecat.transports.whatsapp.client import WhatsAppClient

_session = aiohttp.ClientSession()
_whatsapp_client = WhatsAppClient(
    whatsapp_token=WHATSAPP_TOKEN,        # Meta permanent access token
    phone_number_id=WHATSAPP_PHONE_NUMBER_ID,  # Phone number ID from Meta
    session=_session,
    whatsapp_secret=WHATSAPP_APP_SECRET,  # Optional — HMAC validation
)
```

## Per-Call Pipeline

The `connection_callback` receives `(connection: SmallWebRTCConnection, call: WhatsAppConnectCall)`.

`call` object contains:
- `From` — caller's phone number (use for CRM lookup)
- `To` — your business number
- `id` — unique call ID
- `direction` — "inbound" or "outbound"

**CRITICAL:** The callback signature changed in Pipecat 1.4.0. The single-argument `(connection)` form is deprecated. Always use `(connection, call)`.

```python
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.whatsapp.api import WhatsAppConnectCall

async def spawn_whatsapp_bot(connection: SmallWebRTCConnection, call: WhatsAppConnectCall):
    """Called per incoming call — spawns full Pipecat pipeline."""
    
    # Resolve CRM context from caller's phone
    caller_context = await _resolve_caller_context(call, http)
    
    # Build the pipeline with SmallWebRTCTransport (same as browser WebRTC)
    transport = SmallWebRTCTransport(
        webrtc_connection=connection,  # ← from WhatsAppClient, not runner_args
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_passthrough=True,
        ),
    )
    
    # ... STT, LLM, TTS, pipeline build (same as browser agent) ...
    
    worker = PipelineWorker(pipeline, params=PipelineParams(...))
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    await runner.run()
```

## CRM Context Injection

Unlike browser WebRTC (single known user), WhatsApp calls need **per-caller** context:

```python
async def _resolve_caller_context(call: WhatsAppConnectCall, http) -> dict:
    caller_phone = "".join(c for c in (call.From or "") if c.isdigit())
    
    resp = await http.post(
        f"{ARA_BASE_URL}/api/voice/context",
        json={"secret": ARA_VOICE_SECRET, "tenant_id": TENANT_ID, "phone": caller_phone},
        timeout=5.0,
    )
    # Returns: {name, role, actions, pipeline, meetings}
```

Inject into system prompt:
```python
system_prompt += f"""
CURRENT CALLER: {context['caller_name']}
OPEN ACTIONS: {context['open_actions']}
PIPELINE: {context['pipeline_summary']}
TODAY'S MEETINGS: {context['todays_meetings']}
"""
```

## Multi-Call Handling

Each call spawns an independent Pipecat pipeline. `WhatsAppClient` manages the call lifecycle:
- `_ongoing_calls_map` — tracks active WebRTC connections per call_id
- Terminate events clean up connections
- `terminate_all_calls()` on shutdown

## Environment Variables

```bash
WHATSAPP_TOKEN=                   # Meta permanent access token
WHATSAPP_PHONE_NUMBER_ID=         # Phone number ID
WHATSAPP_WEBHOOK_VERIFY_TOKEN=    # Any string — must match Meta dashboard
WHATSAPP_APP_SECRET=              # Optional — enables HMAC validation
```

## Differences from Browser WebRTC Agent

| | Browser (SmallWebRTC) | WhatsApp Calling |
|---|---|---|
| Trigger | JS `pcClient.connect()` | Meta webhook POST |
| WebRTC connection | `runner_args.webrtc_connection` | `WhatsAppClient._handle_connect_event()` creates it |
| Caller identity | Single user (Greg) | Per-call — resolved from `call.From` |
| Pipeline lifetime | Server process lifetime | Per-call — pipeline exits on hangup |
| Webhook server | Not needed (embedded in runner) | Required — FastAPI server on separate port |
| auth | `/api/voice/session` token (browser) | Meta access token + HMAC validation |
| ICE servers | Auto-detected by runner | Configurable via `WhatsAppClient(ice_servers=...)` |
