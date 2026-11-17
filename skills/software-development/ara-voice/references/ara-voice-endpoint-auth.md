# ARA Voice Endpoint Auth — Correct Transport Mechanisms

## Endpoints and Their Auth Requirements

| Endpoint | Method | Auth Location | Example |
|----------|--------|--------------|---------|
| `/api/voice/tools` | GET | **Query param** `?secret=` | `httpx.get(url, params={"secret": secret})` |
| `/api/voice/session` | POST | None (no auth) | `httpx.post(url)` |
| `/api/voice/session/verify` | POST | **JSON body** `{"secret": "..."}` | `httpx.post(url, json={"secret": secret, "token": token})` |
| `/api/voice/tool` | POST | **JSON body** `{"secret": "..."}` | `httpx.post(url, json={"secret": secret, "tool": name, ...})` |

## Common Pitfall

**DO NOT use custom headers.** None of the endpoints read `X-Voice-Secret` or any custom header. Sending via `headers={"X-Voice-Secret": secret}` ALWAYS produces 401, regardless of whether the secret value is correct.

```python
# ❌ Always 401 — ARA never reads this header
headers={"X-Voice-Secret": secret}

# ✅ Correct for GET
params={"secret": secret}

# ✅ Correct for POST
json={"secret": secret, ...}
```

## Server-Side Code (for reference)

```python
# GET /api/voice/tools
@app.get("/api/voice/tools")
def voice_tools(secret: str = ""):
    if secret != ARA_VOICE_SECRET:
        return _JSONResponse({"error": "unauthorized"}, status_code=401)

# POST /api/voice/session/verify
@app.post("/api/voice/session/verify")
def voice_session_verify(data: dict):
    if data.get("secret", "") != ARA_VOICE_SECRET:
        return _JSONResponse({"error": "unauthorized"}, status_code=401)

# POST /api/voice/tool
@app.post("/api/voice/tool")
def voice_tool(data: dict):
    if data.get("secret", "") != ARA_VOICE_SECRET:
        return _JSONResponse({"error": "unauthorized"}, status_code=401)
```

The inconsistency (query param vs JSON body) exists because `GET` requests shouldn't have bodies. Tools and verify use POST so they read from the JSON body. Tools uses GET because it's a data fetch.

## Debugging

If you get 401 from any voice endpoint:
1. Verify the secret matches between `/opt/ara/.env` and `/opt/ara-voice-agent/.env`
2. Check you're sending via the correct mechanism (params vs json body, not headers)
3. Confirm `load_dotenv` ran BEFORE the import that reads `os.getenv("ARA_VOICE_SECRET")`
