# Model Router Pattern — Config-Driven LLM Selection for Voice Agents

Voice agents have different latency requirements than text agents. A model that works perfectly in `agent_chat` (1-3s TTFT is fine for text) is unusable for voice (>1s TTFT kills conversational feel). The model router pattern lets you swap providers/models via environment variables — zero code changes.

## Pattern

```python
import os

# All config-driven — no hardcoded provider assumptions
LLM_PROVIDER = os.getenv("VOICE_LLM_PROVIDER", "groq")
LLM_MODEL = os.getenv("VOICE_LLM_MODEL", "llama-3.3-70b-versatile")
LLM_API_KEY = os.getenv("VOICE_LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("VOICE_LLM_BASE_URL", "")
LLM_TEMPERATURE = float(os.getenv("VOICE_LLM_TEMPERATURE", "0.3"))

def _resolve_llm():
    """Build LLM service based on config. All providers use OpenAI-compatible APIs."""
    provider = LLM_PROVIDER.lower()

    if provider == "groq":
        base_url = "https://api.groq.com/openai/v1"
        api_key = LLM_API_KEY or os.getenv("GROQ_API_KEY", "")
    elif provider == "deepinfra":
        base_url = "https://api.deepinfra.com/v1/openai"
        api_key = LLM_API_KEY or os.getenv("DEEPINFRA_API_KEY", "")
    elif provider == "vertex":
        base_url = LLM_BASE_URL  # Must be set explicitly for Vertex
        api_key = LLM_API_KEY
    else:
        # openai, deepseek, or any OpenAI-compatible
        base_url = LLM_BASE_URL or None
        api_key = LLM_API_KEY

    kwargs = dict(api_key=api_key, model=LLM_MODEL, temperature=LLM_TEMPERATURE)
    if base_url:
        kwargs["base_url"] = base_url

    return OpenAILLMService(**kwargs)
```

## Why OpenAILLMService for all providers

Groq, DeepInfra, and many inference providers expose **OpenAI-compatible endpoints**. `OpenAILLMService` with a `base_url` override works for all of them. No need for separate service classes per provider — the Python `openai` library handles the differences.

## Voice vs Text Models — Different Requirements

| | Text Agent (`agent_chat`) | Voice Agent (WhatsApp/browser) |
|---|---|---|
| TTFT requirement | < 3s acceptable | < 500ms target, < 1s hard limit |
| Turn length | Multi-turn, reasoning-heavy | Single-shot, tool-call-and-narrate |
| Model | DeepSeek V4 (reasoning) | Groq/Llama (speed) |
| Temperature | 0.7 | 0.3 (faster, more deterministic) |
| Streaming | Optional | Required (TTS needs first token fast) |

## Known Latency Benchmarks (July 2026)

| Provider + Model | TTFT | Best for |
|---|---|---|
| Groq + Llama 3.3 70B | 200-300ms | Voice default |
| DeepInfra + DeepSeek V3.2 | 820ms | Text fallback for voice |
| DeepSeek native API + V4 | 1,900ms | Text only — NOT voice |
| Google Vertex + Gemini Flash | 200-300ms | Fast alternative |
| OpenAI + GPT-4.1-mini | 400-800ms | Voice if tool-calling needed |

## Empirical Gate Before Committing

Before locking a voice model, measure:
1. **Tool-call accuracy** — does the fast model hit CRM tools as reliably as the reasoning model?
2. **Latency from India** — US benchmarks don't account for RTT from Indian users
3. **Code-switching** — Hindi + English mid-sentence handling

A fast wrong answer is worse than a slow right one. Don't choose on latency alone.
