# LLM API Truncation Detection

A debugging pattern for detecting and handling truncated LLM responses (when the model runs out of token budget mid-generation).

## The Two Root Causes

| Cause | Signal | Fix |
|-------|--------|-----|
| `max_tokens` too low | API `finish_reason: "length"` (OpenAI) / `stop_reason: "max_tokens"` (Anthropic) | Bump `max_tokens` to ~2x estimated output length in tokens |
| Model naturally stops early | Ends mid-sentence without punctuation | Text heuristic fallback + auto-retry |

## The Definitive Signal: `finish_reason`

**Always check this first.** Every major LLM API returns a field explaining why generation stopped:

- **OpenAI** (`/v1/chat/completions`): `choices[0].finish_reason` — `"stop"` = natural end, `"length"` = hit token limit, `"content_filter"`, `"tool_calls"`
- **Anthropic** (`/v1/messages`): `stop_reason` — `"end_turn"` = natural end, `"max_tokens"` = hit limit

```python
# OpenAI
choice = data["choices"][0]
content = choice["message"]["content"]
truncated = choice.get("finish_reason") == "length"

# Anthropic
stop_reason = data.get("stop_reason", "unknown")
truncated = stop_reason == "max_tokens"
```

**Rule:** If `finish_reason == "length"`, the response is DEFINITIVELY incomplete. Don't rely on text heuristics alone — this is certain.

## Text Heuristic Fallback

When `finish_reason` is `"stop"` but text looks truncated, use heuristics:

```python
def is_argument_complete(content, api_truncated=False):
    if api_truncated:
        return False  # API confirmed truncation
    
    text = content.strip()
    if not text: return False
    if text.startswith("[Error:"): return False
    if len(text) < 50: return False
    
    last_char = text[-1]
    
    # Ends with sentence punctuation = complete
    if last_char in '.!?': return True
    
    # Ends with closing quote wrapping sentence punctuation
    stripped = text.rstrip('\'"\u201d\u201c')
    if stripped and stripped[-1] in '.!?': return True
    
    # Common truncation signals
    if text.endswith(',') or text.endswith(';'): return False
    if text.endswith('..') or text.endswith('...'): return False
    
    # Ends mid-word without punctuation
    if last_char.isalpha():
        # Check if last word is a conjunction (likely cut off mid-clause)
        last_word = re.findall(r'\b\w+\b', text)[-1]
        if last_word.lower() in ('and', 'but', 'or', 'the', 'because', ...):
            return False
        # Unmatched markdown code block
        if text.count('```') % 2 != 0: return False
    
    if last_char.isalpha() or last_char.isdigit():
        return False
    
    return True
```

## Setting `max_tokens`

**Rule of thumb:** Set `max_tokens` to ~2x your expected maximum output in tokens.

- English: ~1.3 tokens per word (0.75 words per token)
- Chinese: ~2 characters per token
- DeepSeek: similar to OpenAI tokenization (~0.7 words/token for English)

**Example:** If the prompt asks for 200-350 words:
- Expected max output: 350 words × 1.3 = ~455 tokens
- Set `max_tokens`: 1000-1200 (2x headroom)
- If the prompt also includes history (debate context, conversation history, etc.), those are INPUT tokens — they don't affect the output budget. Only `max_tokens` matters for output length.

**The trap:** Setting `max_tokens` too close to the expected output (e.g., 800 tokens for 350-word prompts). The model may try to produce more than instructed, hit the ceiling, and get forcibly truncated. This is the most common cause of "incomplete arguments" in LLM apps.

## Auto-Retry Pattern

Use as a safety net, not a strategy:

```python
async def call_with_validation(model_key, system_prompt, user_prompt, max_retries=1):
    for attempt in range(max_retries + 1):
        result = await call_llm(model_key, system_prompt, user_prompt)
        content = result["content"]
        truncated = result["truncated"]  # from finish_reason
        
        if is_argument_complete(content, api_truncated=truncated):
            return (content, False, attempt)  # success
        
        if attempt < max_retries:
            await asyncio.sleep(0.5)  # brief cooldown before retry
    
    return (content, True, max_retries)  # exhausted — content may be incomplete
```

**Design principle:** If retries reliably succeed (first attempt fails, second works), the generation parameters are wrong — bump `max_tokens` or adjust the prompt. Retries should be a rare safety net, not a regular part of the flow.

## Regeneration Endpoint (for interactive apps)

When content is incomplete after all retries, provide a way to regenerate the last turn:

```
POST /api/chamber/{session_id}/regenerate
```

- Rebuilds the prompt with the SAME stage/context but WITHOUT the truncated response
- Overwrites the last entry in history (no duplicates)
- Uses the same validation pattern so the new result is checked for completeness
- Frontend displays a retry button only when `complete: false`

## Real-World Case Study

**Chamber Debate App** (`/Users/greg/Documents/debate_app/debate_server.py`):

- **Symptom:** Arguments frequently came back half-generated; user had to manually retry
- **Initial fix:** Added `is_argument_complete()` + `call_llm_with_retry()` + regenerate endpoint + UI warnings
- **Root cause found later:** `max_tokens: 800` was too low for 200-350 word arguments once debate history grew
- **Actual fix:** Raised `max_tokens` to 1600 (2x headroom) + added `finish_reason` check from API
- **Result:** Arguments jumped from ~800 chars (often truncated) to 1,800-2,400 chars (consistently complete). Retries went from "frequently needed" to "never needed in testing."

**Lesson:** The first fix (retry + UI) was a band-aid. The real fix was the generation parameter. Always check generation parameters before building compensatory mechanisms.
