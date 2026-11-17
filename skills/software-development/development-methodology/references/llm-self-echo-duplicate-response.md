# LLM Self-Echo: Duplicate Content in Agent Responses

## Problem

An LLM agent generates a response that contains the same content twice within a single message. The duplication is not random text generation — it follows a specific code-path cause.

## Root Cause

**Injecting the model's own response as an assistant message before re-calling it.**

```python
# BAD — causes self-echo
messages.append({"role": "assistant", "content": response_clean})  # model sees own text
messages.append({"role": "user", "content": follow_up})            # told to respond again
response = call_llm(messages)  # new response duplicates old content
```

The flow:
1. Model generates Response A containing text + tool call markers
2. Tool call markers are stripped → `response_clean`
3. Model is re-called with `response_clean` as an assistant message
4. The follow-up says "Respond naturally" — model sees its own text and echoes it
5. Final response contains the same content twice (Response A + echoed version)

## Detection

The symptom is specific: **the exact same text appears twice within a single response**, not across multiple messages. The user says "she repeated the same message again within the same message."

Check the `agent_chat` endpoint (or equivalent) for this pattern:
```
grep -n 'response_clean.*role.*assistant' server.py
```

## Fix

Two changes:

### 1. Remove `response_clean` injection

Do NOT add the model's cleaned response back into the conversation history for the second call:

```python
# BAD — causes self-echo
messages.append({"role": "assistant", "content": response_clean})

# GOOD — skip it entirely. The follow_up with tool results is enough.
messages.append({"role": "user", "content": follow_up})
```

### 2. Add explicit "do not repeat" instruction

The follow-up message should tell the model not to restate itself:

```
BAD: "The user is still waiting for your response. Summarize what was done..."
    → model interprets this as "restate + add"

GOOD: "DO NOT repeat what you already said — the user saw it. Respond naturally."
    → model knows the user already has the first response
```

## Complete Before/After

```python
# BEFORE:
follow_up = "The user is still waiting for your response. Summarize what was done."
messages.append({"role": "assistant", "content": response_clean})
messages.append({"role": "user", "content": follow_up})

# AFTER:
follow_up = "DO NOT repeat what you already said — the user saw it. Respond naturally."
messages.append({"role": "user", "content": follow_up})
```

## Broader Pattern

This is a specific case of a general problem: **never feed an LLM its own output as context unless you want it to reference or extend that output.** When you do:

- The LLM treats the injected text as its own prior response
- It may incorporate, restate, or paraphrase it in the new response
- The follow-up instruction determines whether it summarizes, extends, or echoes

The fix pattern applies to any system where:
1. An LLM generates text with embedded control markers
2. The markers are stripped
3. The cleaned text is fed back for a second generation pass

## Real-World Occurrence

**System:** ARA's agent chat endpoint (`server.py` POST `/api/agent/chat/{tenant_id}`)

The fix was applied in June 2026 across both the **confirmed** and **unconfirmed** tool-execution code paths (two branches with identical patterns).
