# Native Function Calling Build Spec — ARA Agent Loop (June 2026)

**Source:** External technical advisor review, commissioned June 13, 2026.
**Context:** ARA's agent loop (`agent_chat` in `server.py`) used text-marker `[TOOL_CALL: {...}]` parsing with a balanced-brace scanner. The advisor recommended switching to native OpenAI-compatible function calling with an observe-then-continue loop.
**Status:** Parts 1, 3, 6a, 6b complete. Parts 2, 4, 5, 7 in progress.

## Problem Statement

The agent loop had two independent failure modes:

1. **Text-marker `[TOOL_CALL:]` parsing** — 60 lines of balanced-brace matching with manual string escape handling and JSON re-parsing (`_parse_tool_calls`). This breaks on nested braces, malformed JSON, missing closing brackets — all silently dropping tool calls.

2. **Correction cascade** — When the model produced text without a tool call, three separate corrector blocks (enforcer re-call, phantom-update corrector, phantom-lookup corrector) spent 2-3 extra Pro calls to recover. Each extra call added latency and increased the chance of hallucination.

## The Fix (7 Parts)

### Part 0 — Confirm transport
- `call_llm` is **blocking** (httpx.post with timeout=60) — no streaming complexity
- DeepSeek supports **OpenAI-compatible native function calling** via `tools` parameter
- `call_llm` returns only text — no `tool_calls` access
- **Finding:** A new function needed, not a modification to existing `call_llm`

### Part 1 — `call_llm_with_tools`
- New function in `induction_engine.py` (line ~129)
- Sends `tools` array + `tool_choice="auto"` in request body
- Returns structured dict: `{text, tool_calls[{id, name, args}], raw_tool_calls, raw, error}`
- Lower temperature (0.2) for tool-deciding turn
- Existing `call_llm` untouched for all non-agent callers (induction, cadence, analysis)
- Unit tests: 4/4 pass (`test_native_tools.py`)
- **Pushed in `29e868e`**

### Part 2 — Observe loop
- Replaces the single-call-then-parse + enforcer + correctors with a bounded loop
- Flow: LLM call → execute tools → feed results back → repeat (up to MAX_TOOL_STEPS=4)
- On first pass: determine intent (NOW/ASK), handle pending confirmation
- Claim/no-call check replaces the keyword-based enforcer
- Dependency skip (DEPENDS_MAP) preserved
- Fallback to legacy `_parse_tool_calls` if native call returns no tools but text contains `[TOOL_CALL:]`
- **Status: Function in server.py, wired into agent_chat. Integration fixes in progress.**

### Part 3 — `build_tools_schema()`
- Generates OpenAI-format JSON schema for all 50 tools in `execute_tool()`
- `TOOL_SCHEMAS` dict with name, description, `read_only` flag
- Coverage test diffs schema keys against execute_tool branches — fails on drift
- `get_tool_read_only(name)` — used for auto-execute gate
- 3/3 test pass (`test_schema_coverage.py`)
- **Pushed in `6841e1c`**

### Part 4 — System prompt (drop-in replacement)
- **Not yet implemented** — Greg has a copy on Desktop
- Will replace tool-rules sections with behavior-focused instructions
- Remove `[TOOL_CALL:]` text-format teaching (API handles format now)
- Keep identity, pipeline-context injection, watchlist blocks
- See the build spec prompt text for the full replacement

### Part 5 — Delete correctors
- Remove: enforcer block, phantom-update corrector, phantom-lookup corrector
- Replace with one `_claims_action_without_call()` check inside the observe loop
- **Status: Function written, not yet wired (depends on Part 2 completion)**

### Part 6 — Logging + fixture
- **6a**: Structured `agent_turn` log line at end of each agent_chat turn
  - Logs: tenant, thread, model, steps, tools_called, tool_args, tool_failures, claim_nudge_fired, reprompt_fired, native_used, intent, executed
- **6b**: 15-conversation offline test fixture
  - Mocks `call_llm_with_tools` with canned responses
  - Covers: stage change, send+confirm, voice note search, web search, duplicate lead, ambiguous lead, question with write-keyword, tool error retry, simple question, chained request, status query, greeting, update with reason, cancel cadence, save learning
  - 15/15 pass
- **Pushed in `50f87cd`**

### Part 7 — Text fallback + deletion ticket
- Keep `_parse_tool_calls` as time-boxed fallback for model swaps / API regressions
- If `call_llm_with_tools` returns no tool_calls but text contains `[TOOL_CALL:]` → fall back to text parser
- Open deletion ticket. Only delete once `agent_chat` shows ~0% fallback rate in logs
- **Status: Not started**

## Key Design Principles

| Principle | Why |
|-----------|-----|
| `tool_choice="auto"` always | Model must be free to answer simple questions with no call |
| No keyword lists | Every heuristic being replaced — observe loop is the real fix |
| No new corrector calls | The observe loop IS the real fix; don't stack more LLM calls on top |
| Lower temperature (0.0-0.3) for tool turns | Creativity hurts tool selection |
| MAX_TOOL_STEPS=4 hard stop | Never unbounded; honest partial summary on timeout |
| `role:"tool"` JSON is model-only | Users see `render_results()` output, never raw tool results |
| Scope = `agent_chat` only | Cadence/induction/learning stay on text `call_llm` |

## Cost Hypothesis

The claim that native calling + observe loop **reduces** total LLM cost is a hypothesis (not yet proven). Rationale:

- Current: single Flash call + enforcer re-call (Pro) + phantom-update corrector (Pro) = 1 Flash + 2 Pro calls
- New: observe loop Pro call + tool results feedback = 1-2 Pro calls (no corrector cascade)

If enforcer fires on 20% of turns, the old path averages 1.4 Pro calls per turn. The new path averages 1.1-1.2 Pro calls per turn. **The structured logging (Part 6a) exists to measure this.** Do not claim cost savings as fact until the numbers confirm it.

## Test Command

```bash
cd /opt/ara && /opt/ara/venv/bin/python3 -m pytest tests/test_conversation_fixture.py tests/test_native_tools.py tests/test_schema_coverage.py -v
```

Expected: 22 passed.
