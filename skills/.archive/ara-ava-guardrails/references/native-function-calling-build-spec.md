# Native Function Calling Build Spec

**Date:** June 13, 2026  
**Scope:** Migrate ARA's `agent_chat` from `[TOOL_CALL: {...}]` text-marker parsing to native OpenAI-compatible function calling.

## Current Architecture (Pre-Migration)

The LLM outputs `[TOOL_CALL: {"tool": "name", "args": {...}}]` as raw text. A 60-line balanced-brace parser (`_parse_tool_calls`, server.py ~line 340) extracts tool calls from this text. The system prompt teaches the text format with examples.

## Target Architecture (Post-Migration)

Tool schemas go in the `tools` API parameter (OpenAI format). The LLM returns structured `response.choices[0].message.tool_calls`. An observe-loop feeds results back so the model can react/retry/chain.

## Build Order

### Part 0 — Confirm Model + Transport (Done June 13)

`call_llm` in `induction_engine.py`:
- No `tools` parameter — needs new variant
- Returns text only — needs to return raw response
- **Blocking** (httpx.post, timeout=60) — no streaming complexity ✅
- DeepSeek supports OpenAI-compatible tool calls ✅

### Part 6 — Baseline (✅ Done June 13)

- Structured per-turn logging (`agent_turn` log line at end of `agent_chat`)
- 15-conversation offline fixture (`tests/test_conversation_fixture.py`) — 15/15 pass

### Part 1 — call_llm_with_tools

New function in `induction_engine.py`:
```python
def call_llm_with_tools(messages, tools, model="deepseek-v4-pro", temperature=0.2):
    # Sends tools=tools in request body, tool_choice="auto"
    # Returns: {"text": str, "tool_calls": [{id, name, args}], "raw_tool_calls": [...], "raw": {...}}
    # On error: {"text": "", "tool_calls": [], "error": str}
```
- Keep existing `call_llm` untouched for non-agent callers
- `tool_choice="auto"` — model must be free to answer without tools
- Lower temperature (0.0–0.3) for tool-deciding turn

### Part 3 — build_tools_schema()

```python
def build_tools_schema():
    # One entry per tool in execute_tool()
    # OpenAI function-calling format with JSON Schema parameters
    # required[] matching execute_tool arg validation
    return [...]  # list of {"type":"function","function":{...}}
```

Coverage assertion: diffs schema entries against `execute_tool()` branches and fails on drift.

### Part 2 — Observe-Loop (Highest Impact)

Replace single-call-then-parse with bounded loop:

```python
MAX_TOOL_STEPS = 4
while steps < MAX_TOOL_STEPS:
    out = call_llm_with_tools(loop_messages, TOOLS_SCHEMA)
    if not out["tool_calls"]:
        # Answer directly, or check claim/no-call mismatch
        break
    # Execute tools
    results = [execute_tool(tc["name"], tc["args"], ...) for tc in out["tool_calls"]]
    # Feed results back
    loop_messages.append({"role":"assistant","content":...,"tool_calls":out["raw_tool_calls"]})
    for tc, r in zip(tool_calls, results):
        loop_messages.append({"role":"tool","tool_call_id":tc["id"],"content":json.dumps(r.to_dict())})
```

This makes the enforcer, phantom-update corrector, and phantom-lookup corrector unnecessary.

### Part 5 — Delete Correctors

Remove:
- `_data_keywords` pre-execution enforcer block
- `update_claim_re` + re-prompt (phantom-update corrector)
- `_lookup_claim_re` + re-prompt (phantom-lookup corrector)

Replace with one helper:
```python
def _claims_action_without_call(text):
    """True if model claims it did/changed/sent something but issued no tool call."""
```

Gate on the mismatch between the model's claim and the absence of a tool call — never on keywords in the user's message.

### Part 4 — Swap System Prompt

Replace `[TOOL_CALL:]`/`[KB:]` text-format teaching with behavior-only instructions. Remove `AGENT_TOOL_SCHEMA` from prompt-append path (tools now go via API parameter). Keep identity, pipeline context, and the non-tool behavior rules.

### Part 7 — Text Fallback

- Keep `_parse_tool_calls` as a time-boxed fallback in `agent_chat`
- If `call_llm_with_tools` returns no tool_calls AND text contains `[TOOL_CALL:`, fall back
- Open deletion ticket — delete once other emit-sites (voice pipeline, auto-respond) are migrated

## Key Constraints

- `MAX_TOOL_STEPS = 4` hard stop, never unbounded
- `tool_choice = "auto"` always — never force a specific tool
- User never sees `role:"tool"` JSON — it's the model's eyes only
- Lower temperature for tool-deciding turn (0.0–0.3)
- Do NOT migrate cadence/induction/learning calls — scope is `agent_chat` only

## Caveat

The claim that native calling + observe-loop reduces total LLM cost is a hypothesis. Part 6 logging confirms or refutes it — compare per-turn call counts before/after.
