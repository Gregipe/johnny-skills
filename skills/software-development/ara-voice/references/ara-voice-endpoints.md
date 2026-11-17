# ARA Voice Endpoints — Phase 1, Read-Only Tool Calling

Date: 2026-07-03

Four new endpoints added to `/opt/ara/server.py` enabling the Pipecat voice
agent to securely call ARA CRM tools.

## Constants

```python
# In server.py, near TOOL_SCHEMAS:
VOICE_SAFE_TOOLS = [
    "search_leads", "query_leads", "get_lead_detail",
    "get_pipeline_summary", "get_summary", "get_action_items",
    "get_activity_log", "search_knowledge_base",
]

# After 'import os, io' (line 89):
ARA_VOICE_SECRET = os.getenv("ARA_VOICE_SECRET", "")
_voice_tokens = {}  # {token: {tenant_id, expires_at}}
```

## Endpoint 1 — POST /api/voice/session

Mints a single-use voice token tied to the server's tenant.

```
POST /api/voice/session
(no auth — same-origin, called by dashboard JS)

Response 200: {"voice_token": "32-byte-urlsafe-random"}
```

Implementation: generates `secrets.token_urlsafe(32)`, stores in
`_voice_tokens[token] = {"tenant_id": TENANT_ID, "expires_at": time() + 60}`.

## Endpoint 2 — POST /api/voice/session/verify

Verifies and **consumes** a voice token. Returns the tenant_id.

```
POST /api/voice/session/verify
Content-Type: application/json
{"secret": "<ARA_VOICE_SECRET>", "token": "<voice_token>"}

Response 200: {"tenant_id": "..."}
Response 401: {"error": "unauthorized"} (bad secret)
Response 401: {"error": "invalid or expired token"} (unknown/reused/expired)
```

**Critical:** uses `_voice_tokens.pop(token)` — single-use. Token deleted on
first read. Reuse or expiry returns 401.

## Endpoint 3 — GET /api/voice/tools

Returns read-only tool metadata for the voice agent.

```
GET /api/voice/tools?secret=<ARA_VOICE_SECRET>

Response 200:
{"tools": [
  {"name": "search_leads", "description": "...", "read_only": true, "parameters": {...}},
  ...
]}
```

Filters `TOOL_SCHEMAS` to tools in `VOICE_SAFE_TOOLS` AND `read_only is True`
(belt-and-braces: write tool accidentally added to `VOICE_SAFE_TOOLS` still
won't pass the `read_only` check).

Returns the full `parameters` schema from `TOOL_SCHEMAS` so the LLM produces
correct argument names.

## Endpoint 4 — POST /api/voice/tool

Executes a read-only tool and returns the result.

```
POST /api/voice/tool
Content-Type: application/json
{"secret": "<ARA_VOICE_SECRET>", "tool": "get_pipeline_summary",
 "args": {}, "tenant_id": "..."}

Response 200:
{"ok": true, "tool": "get_pipeline_summary", "summary": "Pipeline: 30 leads, 16 deals...", ...}
```

Enforcement (in order):
1. `secret` matches `ARA_VOICE_SECRET` → 401 if not
2. Tool name in `VOICE_SAFE_TOOLS` → `{"ok": false, "message": "not available for voice"}` if not
3. `TOOL_SCHEMAS[tool].get("read_only") is True` → `{"ok": false, "message": "write-only"}` if not
4. Calls `execute_tool(tool_name, args, db, wa, tenant_id)`
5. Returns `ToolResult` as JSON (strings become `{ok: true, summary: str}`)

On exception: `{"ok": false, "message": str(e)[:200]}`, HTTP 200 (voice handler
converts to spoken error; a 500 would hang the tool call).

## Token Auth Flow

```
Browser (dashboard)                    Pipecat (voice agent)              ARA server
      │                                       │                              │
      │── POST /api/voice/session ────────────│─────────────────────────────>│
      │<─ {voice_token} ──────────────────────│──────────────────────────────│
      │                                       │                              │
      │── POST /start {voice_token} ─────────>│                              │
      │                                       │── POST /verify {secret,token}>│
      │                                       │<─ {tenant_id} ───────────────│
      │                                       │                              │
      │<─ WebRTC established ─────────────────│                              │
      │                                       │── GET /tools?secret= ───────>│
      │                                       │<─ [FunctionSchemas] ─────────│
      │                                       │                              │
      │  "Show my pipeline" ─────────────────>│                              │
      │                                       │── POST /tool {secret,...} ──>│
      │                                       │<─ {ok:true, summary:"..."} ──│
      │<─ "You have 30 leads..." (TTS) ───────│                              │
```

## Security Rules

- `X-Voice-Secret` is server-to-server only (Pipecat ↔ ARA, both on localhost)
- `tenant_id` never originates from browser — always server-derived
- Tokens are single-use (pop on read), 60s TTL
- Gate test T1: `grep X-Voice-Secret /opt/ara/dashboard_template.py` → empty
- Gate test T2: `/api/voice/session` → token → verify → OK; second verify → 401
- Gate test T3: tool not in list → refused; write tool → refused by read_only check
- Gate test T4: tenant_id in execution matches the one from verify

## Insertion Points in server.py

- `ARA_VOICE_SECRET` + `_voice_tokens = {}`: after `import os, io` (line 89) — NOT before!
- `VOICE_SAFE_TOOLS`: before `def build_tools_schema():`
- 4 endpoints: before `if __name__ == "__main__":` (line ~12821)

## Patching Pitfall — `import os` Ordering

`server.py` imports `os` at line 89 as `import os, io` (combined import).
Inserting `ARA_VOICE_SECRET = os.getenv(...)` BEFORE this line causes
`NameError: name 'os' is not defined`. The fix: insert AFTER `import os, io`.

Do NOT rely on `import os` being a standalone line — it's combined with `io`.
