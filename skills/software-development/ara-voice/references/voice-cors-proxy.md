# Voice CORS Proxy

When the ARA dashboard (`https://ara.move78.work`) needs to connect to the Pipecat voice agent (on a different origin — ngrok or localhost:8768), the browser blocks cross-origin `/start` fetches with CORS errors.

## Problem

```
Origin https://ara.move78.work is not allowed by Access-Control-Allow-Origin.
Status code: 502
```

The Pipecat runner allows all origins (`Allowed origins: all (no restriction)`) but the ngrok/proxy layer may not forward CORS headers correctly, or the HTTPS→HTTP downgrade causes issues.

## Solution: Same-origin proxy through ARA

Add a catch-all proxy to ARA's FastAPI server that forwards `/voice/*` to the Pipecat server on localhost:8768. This makes the voice endpoints same-origin with the dashboard.

### ARA server.py changes

```python
# Add imports
from starlette.responses import Response
from fastapi import Request

# Add proxy endpoint (before if __name__ == "__main__":)
@app.api_route("/voice/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def voice_proxy(path: str, request: Request):
    """Proxy voice WebRTC requests to Pipecat on localhost:8768."""
    import httpx
    client = httpx.AsyncClient(timeout=30.0)
    url = f"http://localhost:8768/{path}"
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
    try:
        resp = await client.request(
            method=request.method, url=url,
            headers=headers, content=body or None,
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
        )
    finally:
        await client.aclose()
```

### Dashboard JS change

```javascript
// Old (CORS-broken):
const VOICE_ENDPOINT = 'https://supportlessly-fourcha-inez.ngrok-free.dev/start';

// New (same-origin):
const VOICE_ENDPOINT = '/voice/start';
```

### Prerequisites

- `httpx` must be installed in ARA's venv: `pip install httpx`
- Pipecat must be running on localhost:8768
- Restart ARA: `systemctl restart ara-server`

### Verification

```bash
# Both should return a sessionId
curl -s -X POST http://localhost:8766/voice/start
curl -s -X POST http://localhost:8768/start
```

### Pitfalls

- **The `Request` import must be `from fastapi import Request`**, not `from starlette.requests import Request`. FastAPI auto-injects `Request` parameters; Starlette's does not. Using the wrong import causes `{"detail":[{"type":"missing","loc":["query","request"],"msg":"Field required"}]}` on every call.
- **`import httpx` inside the function** avoids adding it as a permanent dependency. If httpx is already in the ARA venv, it works. If not, install it first.
- **The proxy forwards ALL paths under `/voice/`** — including `/voice/api/offer`, `/voice/sessions/{id}/api/offer`, etc. This is intentional.
- **The proxy does NOT handle WebSocket** — WebRTC signaling is HTTP-only (POST/PATCH). Media flows over UDP directly.
