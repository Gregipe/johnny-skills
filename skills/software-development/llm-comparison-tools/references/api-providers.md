# API Provider Configuration (Gregory's Setup)

## DeepSeek (OpenAI-Compatible)

| Field | Value |
|-------|-------|
| Base URL | `https://api.deepseek.com/v1` |
| API Key | `sk-e05b9ee0fc5441b594aa28104d17c84f` |
| Auth Header | `Authorization: Bearer <key>` |
| Chat Endpoint | `POST /chat/completions` |
| Models | `deepseek-v4-flash`, `deepseek-v4-pro` |
| Available Models | Fetch from `GET /models` |

### Request Format (curl)

```bash
curl -s "https://api.deepseek.com/v1/chat/completions" \
  -H "Authorization: Bearer sk-e05b9ee0fc5441b594aa28104d17c84f" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v4-flash",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100,
    "temperature": 0.7
  }'
```

### Python (httpx)

```python
async with httpx.AsyncClient(timeout=60.0) as client:
    resp = await client.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model_id, "messages": msgs, "max_tokens": 800, "temperature": 0.7}
    )
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
```

---

## MiniMax (Anthropic-Compatible)

| Field | Value |
|-------|-------|
| Base URL | `https://api.minimax.io/anthropic/v1` |
| API Key | `sk-api-XrHAQxjor9j5X18KwMS2TQjsE_HUy4A-FjbCYzJbqQ-hEIDgiy1bRNSpopwrCCbw0reuAXgCFYmLZiHTyx7uiKQOiI4cnHcJ9eJZCh7UyX4QCMcQl-BFEI4` |
| Auth Header | `x-api-key: <key>` |
| Extra Header | `anthropic-version: 2023-06-01` |
| Chat Endpoint | `POST /messages` |
| Models | `MiniMax-M2.5`, `MiniMax-M2.7`, `MiniMax-M2.7-highspeed` |

### Key Differences vs OpenAI

- Uses `x-api-key` header (not `Authorization: Bearer`)
- Requires `anthropic-version` header
- Message format uses `system` as a top-level param, not in messages array
- Response uses `content` array with `type: text` blocks
- Has `thinking` blocks in responses (interleaved with text content)
- Model IDs differ from the config.yaml names

### Request Format (curl)

```bash
curl -s "https://api.minimax.io/anthropic/v1/messages" \
  -H "x-api-key: sk-api-..." \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "MiniMax-M2.5",
    "max_tokens": 100,
    "system": "You are a helpful assistant.",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Python (httpx)

```python
async with httpx.AsyncClient(timeout=60.0) as client:
    resp = await client.post(
        "https://api.minimax.io/anthropic/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        },
        json={
            "model": "MiniMax-M2.5",
            "max_tokens": 800,
            "temperature": 0.7,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}]
        }
    )
    data = resp.json()
    text = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            text += block.get("text", "")
```

### Response Structure

```json
{
  "id": "...",
  "type": "message",
  "role": "assistant",
  "model": "MiniMax-M2.5",
  "content": [
    {"thinking": "...", "signature": "...", "type": "thinking"},
    {"text": "Hello!", "type": "text"}
  ],
  "usage": {"input_tokens": 27, "output_tokens": 19}
}
```

Note: MiniMax responses include `thinking` blocks before `text` blocks. Always iterate the `content` array to find the `type: "text"` block.

---

## Rate Limits & Pitfalls

| Provider | Limit | Notes |
|----------|-------|-------|
| DeepSeek | Generous (no observed hard limits at normal usage) | 60s timeout is sufficient |
| MiniMax | ~10 RPM on global endpoint | Responses include thinking blocks that count toward output tokens. Space calls if hitting 1002 errors. |

- MiniMax error `status_code: 1002` = rate limit exceeded (RPM). Wait 6+ seconds between calls.
- MiniMax China endpoint (`api.minimaxi.com`) uses the same API key but different base URL.
