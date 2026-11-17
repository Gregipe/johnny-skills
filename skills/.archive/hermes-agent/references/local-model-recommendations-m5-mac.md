# Local Model Recommendations — Apple Silicon (M5 32GB)

Gregory's setup: MacBook Pro M5, 32GB RAM, LM Studio for local hosting.

## By Task

### Thinking / Planning / Orchestration
- **Primary:** `claude-sonnet-4-6` (Anthropic, cloud) — no local model matches it for complex reasoning
- **Local backup:** `deepseek-r1-distill-qwen-14b` — genuine reasoning model, runs well on M5 32GB

### Coding
- **Primary:** `qwen/qwen2.5-coder-14b` (LM Studio local) — best-in-class local coding model
- **Cloud fallback:** Claude Sonnet for complex/gnarly problems
- Hermes delegation config: `provider=openai`, `base_url=http://localhost:1234/v1`, `api_key=lm-studio`

### Research / Web Search
- **MiniMax 2.5** (cloud) — 1M token context window, great for ingesting long docs/papers
- Set up via `MINIMAX_API_KEY` in `~/.hermes/.env`

### Auxiliary Tasks (compression, title_generation, etc.)
- **Option A (cloud):** `claude-haiku-3-5` via Anthropic — fast and cheap
- **Option B (local):** `llama-3.2-3b` or `qwen2.5:3b` via LM Studio — free, very fast on M5

## LM Studio Models to Pull
- `deepseek-r1-distill-qwen-14b` — planning/orchestration backup
- `qwen2.5-coder-14b` — coding (already installed)
- `llama-3.2-3b` — aux tasks (lightweight)

## Current Config Status (as of session May 2026)
- Main model: `claude-sonnet-4-6` (Anthropic) ✅
- Delegation: `qwen/qwen2.5-coder-14b` via LM Studio ✅
- All auxiliary tasks: `claude-haiku-3-5` (Anthropic) ✅
- MiniMax for research: not yet configured
- deepseek-r1 local backup: not yet pulled
