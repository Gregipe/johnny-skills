# render_results Swallowing LLM Synthesis — June 16, 2026

## Symptom

STRATEGIC and DIAGNOSTIC queries returned "✅ 9 action(s) completed" instead of actual analysis. The LLM gathered data correctly (pipeline summary, lead lists, web search), but the user only saw the tool confirmation text, not the synthesis.

**Before:** "Where should I get my next leads?" → "✅ 9 action(s) completed"
**After:** "Where should I get my next leads?" → Full pipeline analysis with segment gaps and 3 target recommendations

## Root Cause

The observe loop (`_run_observe_loop`) correctly captures both:
- `final_text`: the LLM's synthesis/analysis text
- `response`: `render_results(all_results)` — the tool confirmation text ("✅ 9 action(s) completed")

But `agent_chat()` at line 6262 returned `response` (render_results) to the user, completely ignoring `final_response_text`:

```python
# agent_chat() line 6189 — extracts the LLM's synthesis
final_response_text = _loop_out["final_text"]

# agent_chat() line 6262 — but returns tool confirmations instead
return {"response": response, ...}  # ← BUG: response = render_results
```

The LLM's `final_text` was captured at line 5716 of the observe loop:
```python
"final_text": final_text or response,
```

It was extracted at line 6189. But it was NEVER used in the return at line 6262.

## Fix

One-line change at agent_chat() line 6262:
```python
# Before
return {"response": response, "thread_id": thread_id, "tool_results": _tool_results_json}

# After  
return {"response": final_response_text or response, "thread_id": thread_id, "tool_results": _tool_results_json}
```

When `final_response_text` exists (LLM produced analysis), the user sees that. When it doesn't (LLM just made tool calls with no text), the user sees the render_results summary as fallback.

## Verification

Tested with STRATEGIC query "Analyze my pipeline. What verticals am I missing?":
- Before: 30 chars ("✅ 9 action(s) completed")  
- After: 2,193 chars — full segment analysis, 3 gaps identified, 3 targets with rationale

## Related

- `tool-failure-patterns-june16.md` — query_database text() wrapper, create_action due_at defaults, create_lead placeholder rejection
- `message-classification-architecture.md` — the classification system that drives STRATEGIC/DIAGNOSTIC mode
