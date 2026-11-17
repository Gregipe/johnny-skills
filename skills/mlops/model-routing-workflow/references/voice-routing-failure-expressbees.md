# Voice Note Routing Failure — ExpressBees (June 13, 2026)

## Status: RESOLVED — Pro-by-default migration

This bug was the catalyst for the broader Pro-by-default migration on June 13, 2026. See SKILL.md → "Architecture History" for the full migration story.

## The Bug

Voice note at 8:34 AM IST (03:04 UTC):
> "Hey Eva, I have a meeting with ExpressBees, could you give me two lines about latest news about them?"

Pipeline log:
```
03:04:40  Transcribed (10s): "Hey Eva, I have a meeting with ExpressBees..."
03:04:40  Model routing: keywords=False, model=deepseek-v4-flash
03:04:41  POST to DeepSeek API → 200 OK
03:04:42  ENFORCER SKIPPED: intent=False has_data_tool=False is_q=True
03:04:43  Response to user: "✅ 1 action(s) completed"
```

## Root Causes

Two independent failures:

### 1. Wrong model (keyword gap)
The phrase "ExpressBees latest news" contains zero routing keywords. The set has `search` and `research` but no `news`, `latest`, `about`, `meeting`, or company-name patterns. Flash got the request despite it needing `web_search`.

**Fix options:**
- Add `news`, `latest`, `meeting` to `_model_routing_keywords`
- Route all voice notes (`🎤 ` prefix) to Pro unconditionally
- Add a regex pattern fallback: `r"\b(news|latest|tell me about|find|look up)\b"`
- Best: regex fallback + voice note prefix check (catches both the broad pattern AND all voice notes)

### 2. Flash hallucinates system-style output
When Flash received the ExpressBees request, it returned `"✅ 1 action(s) completed"` — a message that looks like a server-side callback, not an LLM response. This is a known failure mode for weak models on ambiguous search requests: they default to generic "system completed" language instead of actually calling the search tool.

## Symptoms to Detect

- User asks about news/search/latest about X
- Response is a short system-style message like "✅ N action(s) completed" or "✅ Done"
- No `[TOOL_CALL: web_search]` in the DB assistant message
- Log shows `model=deepseek-v4-flash` and `has_data_tool=False`

## Fix Implemented (June 13, 2026)

**The agent loop was defaulted to deepseek-v4-pro.** The keyword router, regex fallback, and voice-note prefix check were all removed — the agent loop now always uses the reliable tool-caller. See SKILL.md → "Architecture History" for the full rationale.

The interim "fix" (regex + voice-note prefix) was the recommended approach before the broader architectural review concluded that Pro-by-default was simpler and more correct. The regex and voice-note approaches were correct but additive — the Pro-by-default migration eliminated the root cause (a capability fork) rather than patching each gap.

## Original Analysis (Pre-Migration)

Before the Pro-by-default migration, the fix pattern was:

```python
_TOOL_TRIGGER_PATTERNS = re.compile(
    r"\b(news|latest|tell me about|look up|find|search|"
    r"anything about|any news on|update on|research)\b", re.IGNORECASE
)
if msg.startswith("\U0001f3a4") or (_msg_words & _model_routing_keywords) or _TOOL_TRIGGER_PATTERNS.search(msg):
    return "deepseek-v4-pro"
```

This pattern is preserved here in case a future architecture reintroduces a Flash path for the agent loop.
