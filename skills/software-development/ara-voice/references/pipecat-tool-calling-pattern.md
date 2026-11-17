# Pipecat 1.4.0 — CRM Tool Calling Pattern

Date: 2026-07-03 (verified against installed Pipecat 1.4.0 source)

How to inject ARA CRM tools into the voice agent's LLM so it can call
`search_leads`, `get_pipeline_summary`, etc., execute them via HTTP to ARA,
and speak the results.

## Tool Injection

Tools go through `LLMContext`, not `llm.register_function()` (deprecated):

```python
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.processors.aggregators.llm_context import LLMContext

# Build schemas at session startup
schemas = [FunctionSchema(
    name="search_leads",
    description="Search leads by query. Returns matching leads with phone, company, stage.",
    properties={"query": {"type": "string", "description": "Search term"}},
    required=["query"],
    handler=my_handler,  # auto-registered — no separate register_function() call
)]

context = LLMContext(tools=schemas)
```

Confirmed: `FunctionSchema(handler=...)` kwarg exists in
`adapters/schemas/function_schema.py:38` and auto-registration is documented.

## Handler Signature

```python
from pipecat.services.llm_service import FunctionCallParams

async def my_handler(params: FunctionCallParams) -> None:
    """
    params.function_name     — str, the tool name
    params.tool_call_id      — str, unique ID
    params.arguments         — dict, LLM's parsed arguments
    params.result_callback   — call(result_string) → feeds back to LLM → TTS speaks
    params.app_resources     — arbitrary object from PipelineWorker(app_resources=...)
    params.context           — live LLMContext (for pushing frames mid-session)
    """
    result = execute_my_tool(params.arguments, params.app_resources)
    await params.result_callback(result)
```

Key: `params.result_callback(result)` triggers a follow-up LLM completion
whose text flows to TTS automatically. No manual orchestration.

## app_resources Pass-Through

```python
# In bot():
app_resources = {
    "tenant_id": tenant_id,
    "http_client": httpx.AsyncClient(timeout=10.0),
}

worker = PipelineWorker(
    pipeline,
    params=PipelineParams(...),
    app_resources=app_resources,  # ← passed to handler's params.app_resources
)
```

Confirmed: `PipelineWorker(app_resources=...)` exists in `pipeline/worker.py:227`
and is passed through to `FunctionCallParams.app_resources`.

## Runtime Token Verification

```python
import httpx

async def bot(runner_args: RunnerArguments):
    # Extract voice_token from the /start POST body
    voice_token = ""
    if hasattr(runner_args, "body") and isinstance(runner_args.body, dict):
        voice_token = runner_args.body.get("voice_token", "")

    async with httpx.AsyncClient(timeout=10.0) as http:
        # Verify token → get tenant_id from ARA
        tenant_id = "default"
        if voice_token:
            resp = await http.post(
                f"{ARA_BASE}/api/voice/session/verify",
                json={"secret": ARA_VOICE_SECRET, "token": voice_token},
            )
            if resp.status_code == 200:
                tenant_id = resp.json()["tenant_id"]

        # Build tools with the verified tenant
        voice_tools = await build_voice_tools(http)
        app_resources = {"tenant_id": tenant_id, "http_client": http}
        # ... build pipeline with LLMContext(tools=voice_tools) ...
```

Confirmed: `runner_args.body` exists on `RunnerArguments`
(`runner/types.py:160`) and is inherited by `SmallWebRTCRunnerArguments`.

## voice_tools.py — The Complete Pattern

```python
import os, httpx
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

ARA_BASE = os.getenv("ARA_BASE_URL", "http://localhost:8766")
ARA_VOICE_SECRET = os.getenv("ARA_VOICE_SECRET", "")

def _summarize_for_voice(tool_result: dict) -> str:
    if not tool_result.get("ok"):
        return f"Error: {tool_result.get('message', 'unknown error')}"
    return tool_result.get("summary", "Done.")

def make_tool_handler(tool_name: str) -> callable:
    async def handler(params: FunctionCallParams) -> None:
        args = dict(params.arguments)
        tenant_id = params.app_resources["tenant_id"]
        http = params.app_resources["http_client"]
        try:
            resp = await http.post(
                f"{ARA_BASE}/api/voice/tool",
                headers={"X-Voice-Secret": ARA_VOICE_SECRET},
                json={"tool": tool_name, "args": args, "tenant_id": tenant_id},
                timeout=10.0,
            )
            result = _summarize_for_voice(resp.json())
        except httpx.TimeoutException:
            result = "I couldn't reach the CRM just now — it timed out."
        except httpx.ConnectError:
            result = "I couldn't reach the CRM just now."
        except Exception:
            result = "I couldn't reach the CRM just now."
        await params.result_callback(result)
    return handler

async def build_voice_tools(http: httpx.AsyncClient) -> list[FunctionSchema]:
    resp = await http.get(
        f"{ARA_BASE}/api/voice/tools",
        headers={"X-Voice-Secret": ARA_VOICE_SECRET},
        timeout=10.0,
    )
    tools_meta = resp.json()["tools"]
    return [
        FunctionSchema(
            name=t["name"],
            description=t["description"],
            properties=t.get("parameters", {}).get("properties", {}),
            required=t.get("parameters", {}).get("required", []),
            handler=make_tool_handler(t["name"]),
        )
        for t in tools_meta
    ]
```

## Error Handling

Tool handlers must catch ALL exceptions and call `params.result_callback()`
with a spoken-friendly error string. Never let the handler raise — a hung
tool call produces silence, not an error message.

```python
try:
    result = _summarize_for_voice(resp.json())
except httpx.TimeoutException:
    result = "I couldn't reach the CRM just now — it timed out. Try again?"
except Exception:
    result = "I couldn't reach the CRM just now. Try again?"
await params.result_callback(result)
```

## System Prompt

The DASHBOARD_SYSTEM_PROMPT must instruct the LLM to use tools:

```
You are Ava, an AI voice assistant for the user's CRM dashboard.
Spoken-style output: 1–2 sentences, no markdown, no bullet lists.
Use tools for any data question — never fabricate or answer about CRM
data from memory. Summarize results — "you have three logistics leads;
Acme is furthest along" — never enumerate long lists.

If asked to create, update, send, or modify anything: "I can't make
changes by voice yet — I can look anything up for you." Do not propose
write actions or offer to draft them.
```

## Dependencies

Add `httpx>=0.27,<1` to `pyproject.toml`. The `AsyncClient` must outlive
the pipeline session — wrap in `async with` that encompasses `runner.run()`.
