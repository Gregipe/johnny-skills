# Auxiliary Model Setup — Gregory's Config

## Context
Gregory runs Hermes on a MacBook Pro M5 32GB. Main model is claude-sonnet-4-6 (Anthropic).
He wants to minimize Claude token usage by routing auxiliary and delegation tasks to cheaper/local models.

## Model Routing Strategy

| Role | Model | Provider | Notes |
|------|-------|----------|-------|
| Main / Orchestration | claude-sonnet-4-6 | anthropic | Heavy lifting, reasoning |
| Delegation / Coding | qwen/qwen2.5-coder-14b | openai (LM Studio) | Local, `http://localhost:1234/v1` |
| Web extract / Research | MiniMax-M2.5 | minimax | 1M context window, good for long docs |
| All other aux tasks | claude-haiku-3-5 | anthropic | title_generation, compression, session_search, etc. |

## Fallback Chain
```yaml
fallback_providers:
- minimax
- lm-studio
```
MiniMax is primary fallback if Anthropic is down/out of balance. LM Studio is last resort.

## Auxiliary Tasks Configured
All set via `hermes config set auxiliary.<task>.provider` and `auxiliary.<task>.model`:
- `title_generation` → anthropic / claude-haiku-3-5
- `compression` → anthropic / claude-haiku-3-5
- `vision` → anthropic / claude-haiku-3-5
- `web_extract` → minimax / MiniMax-M2.5
- `session_search` → minimax / MiniMax-M2.5
- `skills_hub` → anthropic / claude-haiku-3-5
- `approval` → anthropic / claude-haiku-3-5
- `mcp` → anthropic / claude-haiku-3-5
- `curator` → anthropic / claude-haiku-3-5

## Delegation Config (LM Studio)
```bash
hermes config set delegation.provider openai
hermes config set delegation.model qwen/qwen2.5-coder-14b
hermes config set delegation.base_url http://localhost:1234/v1
hermes config set delegation.api_key lm-studio
```

## LM Studio Notes
- Runs at `http://localhost:1234/v1` (OpenAI-compatible)
- Check available models: `curl -s http://localhost:1234/v1/models | python3 -m json.tool`
- Model IDs include the org prefix, e.g. `qwen/qwen2.5-coder-14b`
- Good models to pull for Gregory's M5 32GB:
  - `qwen2.5-coder-14b` — coding/delegation
  - `deepseek-r1-distill-qwen-14b` — planning/orchestration backup
  - `llama-3.2-3b` or `qwen2.5-3b` — lightweight aux tasks

## MiniMax Notes
- API key in `~/.hermes/.env` as `MINIMAX_API_KEY`
- Balance check (test call):
  ```bash
  curl -s -X POST "https://api.minimax.io/v1/text/chatcompletion_v2" \
    -H "Authorization: Bearer $MINIMAX_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"model": "MiniMax-M2.5", "messages": [{"role": "user", "content": "say hi"}], "max_tokens": 10}'
  ```
- `status_code: 1008` = insufficient balance → top up at https://www.minimax.io
- `status_code: 0` = working fine
- Base URL: `https://api.minimax.io/v1`

## Delegation Context Window Pitfall (LM Studio)

`delegate_task` requires a minimum 64K context window. LM Studio models like `qwen/qwen2.5-coder-14b` report only 4096 tokens by default, causing:
```
Error: Model qwen/qwen2.5-coder-14b has a context window of 4,096 tokens, which is below the minimum 64,000 required by Hermes Agent.
```

Fix by overriding the context length in config:
```bash
hermes config set delegation.context_length 32768
```
Or use a model with a larger native context window.

## faster-whisper on macOS

On macOS, `pip` may not be in PATH — use `pip3`:
```bash
pip3 install faster-whisper
```
Recommended model: `small` (better accuracy than `base`, still fast on M-series chips).
```bash
hermes config set stt.local.model small
```

## Vision 404 Error

If `browser_vision` fails with:
```
Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-haiku-3-5'}}
```
The model name `claude-haiku-3-5` is correct for Hermes config. The 404 here indicates the vision tool is trying to use a different resolution path. Check that `auxiliary.vision.provider` is set to `anthropic` and `auxiliary.vision.model` is `claude-haiku-3-5`. If the issue persists, try the full date-stamped name `claude-3-5-haiku-20241022`.

## Common Warning Messages & Fixes

### "No LLM provider configured for task=title_generation provider=auto"
```bash
hermes config set auxiliary.title_generation.provider anthropic
hermes config set auxiliary.title_generation.model claude-haiku-3-5
```

### "No auxiliary LLM provider configured — context compression will drop middle turns"
```bash
hermes config set auxiliary.compression.provider anthropic
hermes config set auxiliary.compression.model claude-haiku-3-5
```

### Fix ALL auxiliary tasks at once (set to haiku)
```python
tasks = ["vision", "web_extract", "session_search", "skills_hub", "approval", "mcp", "curator", "compression", "title_generation"]
for task in tasks:
    terminal(f"hermes config set auxiliary.{task}.provider anthropic && hermes config set auxiliary.{task}.model claude-haiku-3-5")
```
