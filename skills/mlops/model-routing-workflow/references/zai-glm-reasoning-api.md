# ZAI / GLM-5.2 Reasoning API Reference

## Provider: ZAI (Z.AI / Zhipu AI)

- **Base URL:** `https://api.z.ai/api/paas/v4`
- **Chat completions endpoint:** `https://api.z.ai/api/paas/v4/chat/completions`
- **API key env var:** `GLM_API_KEY` (also accepts `ZAI_API_KEY`, `Z_AI_API_KEY`)
- **Key location (Johnny profile):** `~/.hermes/profiles/johnny/.env` — NOT in ARA's `/opt/ara/.env`
- **OpenAI-compatible:** Yes — same request/response shape as OpenAI `/v1/chat/completions`

## Enabling High Reasoning (Extended Thinking)

GLM-5.2 supports a `thinking` parameter in the request body (NOT `reasoning_effort` like some providers):

```json
{
  "model": "glm-5.2",
  "temperature": 0.2,
  "max_tokens": 8192,
  "thinking": {
    "type": "enabled",
    "budget_tokens": 4096
  },
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ]
}
```

- `budget_tokens` controls how many tokens the model can spend on chain-of-thought reasoning before producing its final answer.
- Higher budget = deeper reasoning but longer latency.
- 4096 is a good default for scope/code reviews; 1024 for simpler tasks.

## Response Shape

The response is OpenAI-compatible, but with an additional `reasoning_content` field:

```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "The final answer...",
      "reasoning_content": "1. Analyze the request...\n2. Formulate the answer..."
    }
  }]
}
```

- `content` — the final answer (what you display/use)
- `reasoning_content` — the chain-of-thought (useful for debugging, not for display)
- When `thinking` is enabled, `content` may be empty and all value is in `reasoning_content` for some queries. Always check both fields.

## Python Usage Pattern (urllib, no dependencies)

```python
import os, urllib.request, json

key = None
with open(os.path.expanduser("~/.hermes/profiles/johnny/.env")) as f:
    for line in f:
        if line.startswith("GLM_API_KEY="):
            key = line.strip().split("=", 1)[1].strip('"').strip("'")
            break

payload = json.dumps({
    "model": "glm-5.2",
    "temperature": 0.2,
    "max_tokens": 8192,
    "thinking": {"type": "enabled", "budget_tokens": 4096},
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
}).encode()

req = urllib.request.Request(
    "https://api.z.ai/api/paas/v4/chat/completions",
    data=payload,
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
)
resp = urllib.request.urlopen(req, timeout=120)
data = json.loads(resp.read())
content = data["choices"][0]["message"]["content"]
reasoning = data["choices"][0]["message"].get("reasoning_content", "")
```

## TA Script (`/tmp/ta_direct.py`)

The TA (Technical Advisor) review script calls GLM-5.2 directly with high reasoning to review scopes and code changes. It is deployed both locally and on the ARA server (`scp`'d to `root@46.224.132.99:/tmp/ta_direct.py`).

**Key points:**
- Loads `GLM_API_KEY` from `~/.hermes/profiles/johnny/.env` (falls back to env var)
- On the ARA server, the key must also be accessible — either copy the key into ARA's `.env` or mount the Hermes profile `.env`
- Uses `thinking: {type: "enabled", "budget_tokens": 4096}` for deep reasoning
- Returns both `content` (verdict) and `reasoning_content` (analysis)

## When to Use GLM-5.2 vs DeepSeek

| Use Case | Model | Why |
|----------|-------|-----|
| TA scope review | GLM-5.2 (high reasoning) | Better analytical reasoning for architecture/scope review |
| ARA agent chat (Ava) | deepseek-v4-pro | Reliable tool-calling, proven in production |
| Induction | deepseek-v4-flash | Fast, conversational, good enough for structured extraction |
| Eval agent | deepseek-v4-flash | Fast JSON extraction from transcripts |
| Hermes main session | glm-5.2 (via zai) | Greg's current default for Hermes CLI sessions |
