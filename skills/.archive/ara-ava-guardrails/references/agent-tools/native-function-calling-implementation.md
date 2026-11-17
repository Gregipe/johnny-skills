# Native Function Calling Implementation (June 13, 2026)

## Overview

Seven-part migration from `[TOOL_CALL: {...}]` text-marker parsing to native OpenAI-compatible function calling. Executed in a single session, deployed to production.

## Build Order

### Part 0 — Confirm Transport
- `call_llm` in `induction_engine.py` is **blocking** (httpx.post, no streaming) ✅
- No `tools` parameter support — needs new variant
- Returns only text string, not raw response object
- DeepSeek supports OpenAI-compatible function calling

### Part 6 — Structured Logging + 15-Conversation Fixture (BASELINE)
Commit: `50f87cd`

**Structured logging** at end of agent_chat:
```python
logger.info("agent_turn", extra={"agent_turn": {
    "tenant": tenant_id, "thread": thread_id, "model": _chat_model,
    "steps": steps, "tools_called": [...], "native_used": bool,
    "intent": intent, "executed": executed,
}})
```

**15-conversation test fixture** at `tests/test_conversation_fixture.py`:
- Mocks `induction_engine.call_llm_with_tools` to return native-format tool calls
- Covers: stage change, send-with-confirm, voice note search, web search, duplicate lead, ambiguous lead, question-with-write-keyword, tool-error-retry, chained request, simple question, greeting, update-with-reason, cancel-cadence, save-learning, pipeline summary

### Part 1 — call_llm_with_tools
Commit: `29e868e`

```python
def call_llm_with_tools(messages, tools, model="deepseek-v4-pro", temperature=0.2):
    """Sends tools parameter to DeepSeek API. Returns:
    {"text": str, "tool_calls": [{"id", "name", "args"}], "raw_tool_calls": [...], "raw": {...}, "error": str}
    """
```

- `tool_choice="auto"` — model free to answer without tools
- Lower temperature (0.2) for tool-deciding turn
- Malformed JSON args captured as `{"_raw": string}`
- Existing `call_llm()` untouched for non-agentic callers (induction, cadence, analysis)

### Part 3 — build_tools_schema() + Coverage Assertion
Commit: `6841e1c`

```python
TOOL_SCHEMAS = {
    "update_lead": {"description": "...", "read_only": False},
    "web_search": {"description": "...", "read_only": True},
    # ... 50 tools total
}

def build_tools_schema():
    """Returns OpenAI-format JSON schema list. Uses TOOL_SCHEMAS dict."""
    return [{"type": "function", "function": {"name": n, "description": m["description"],
        "parameters": {"type": "object", "properties": {}, "additionalProperties": True}}}
        for n, m in TOOL_SCHEMAS.items()]

def get_tool_read_only(name):
    return TOOL_SCHEMAS.get(name, {}).get("read_only", False)
```

**Coverage test** (`tests/test_schema_coverage.py`): diffs `TOOL_SCHEMAS.keys()` against `execute_tool()` branches and fails on drift. Every `elif tool_name == "X"` must have a schema entry, and vice versa.

### Part 2 — Observe Loop
Commit: `9d35f3c` — 260 insertions, 423 deletions

Replaces the single-call-then-parse flow (enforcer + correctors + parse + execute) with `_run_observe_loop()`:

```python
MAX_TOOL_STEPS = 4
while steps < MAX_TOOL_STEPS:
    out = _ie.call_llm_with_tools(loop_messages, tools_schema)
    
    if not out["tool_calls"]:
        legacy = _parse_tool_calls(out["text"])  # fallback
        if not legacy and _claims_action_without_call(out["text"]):
            re-prompt with claim/nudge
            continue
        if not legacy:
            final_text = out["text"]  # model answered directly
            break
    
    # Intent gate (resolved on first pass)
    intent = _parse_execution_intent(text)
    if requires_confirmation and not confirmed:
        store_pending(...)
        break
    
    # Execute tools
    results = [execute_tool(tc.name, tc.args, ...) for tc in tool_calls]
    
    # Feed results back to model
    loop_messages.append({"role": "assistant", "content": text, "tool_calls": raw_tool_calls})
    for tc, r in zip(tool_calls, results):
        loop_messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(r)})
```

### Part 5 — Delete Enforcer + Correctors
Commit: `6fcf707` — 2 insertions, 112 deletions

Removed the phantom-update corrector from `_ava_auto_respond` (~110 lines of LLM re-prompt cascade). The observe loop's claim/no-call check already handles all three cases (enforcer, phantom-update, phantom-lookup) with one function:

```python
def _claims_action_without_call(text):
    """True if prose claims an action but no tool call was made."""
    claim_pats = [
        re.compile(r"...i've|i have|has been|updated|corrected|changed..."),
        re.compile(r"...sent|messaged|texted|emailed|called|contacted..."),
    ]
    return any(p.search(text) for p in claim_pats)
```

### Part 4 — Swap System Prompt
Commit: `6d82b0f` — 311 insertions, 397 deletions

**What was removed:**
- `[TOOL_CALL:]` format teaching (native API handles this now)
- `AGENT_TOOL_SCHEMA` from prompt-append path
- Tool discipline/negative-example sections
- Triple-dat inventory lists (read-only tools, data tools, etc.)
- English-only enforcement line

**What was kept:**
- Identity, pipeline context injection, post-engagement behavior
- Status-questions-from-context section
- System awareness

**What was added:**
- "After a tool runs" — behavior guidance for retry vs report
- "Read vs. write" — [ACTION: NOW] / [ACTION: ASK] intent protocol
- "Sending messages" — draft/approval/confirmation workflow
- "Simple questions override everything above"
- "When you can't" — capability gap logging

### Part 7 — Text Fallback + Deletion Ticket
Commit: `e7b14db`

- Fallback already wired in observe loop (checks for `[TOOL_CALL:]` text markers when native calls are empty)
- `native_used` flag added to structured logging
- `docs/deletion_ticket_parse_tool_calls.md` tracks the eventual removal
- Server restarted and active

## Key Design Decisions

### Why Pro-by-Default (Technical Advisor's Recommendation)
The asymmetry was irreconcilable: a wrong route to Pro costs $0.02-0.05; a wrong route to Flash costs a silently dropped action. The correction cascade (enforcer + phantom-update + phantom-lookup) then spent 2-3 extra Pro calls to claw back, offsetting any cost savings. Flash is kept only for explicitly-invoked non-agentic subtasks where Python code controls the call, not the LLM.

### Why Observe Loop Instead of a Single Native Call
Without result feedback, the model can't:
- Correct a tool call with wrong arguments on its own
- Chain a second tool after the first succeeds
- Learn from errors

The 4-step cap prevents runaway chains while enabling the common patterns (error → retry, success → chain).

### Why Not to Force tool_choice
`tool_choice="auto"` lets the model answer simple questions with zero tool calls. Forcing a specific tool or forcing `"any"` would burn tokens on every simple query.

## Files Changed

| File | Changes |
|------|---------|
| `induction_engine.py` | Added `call_llm_with_tools()` |
| `server.py` | Added `_run_observe_loop()`, `build_tools_schema()`, `TOOL_SCHEMAS`, `_claims_action_without_call()`, `get_tool_read_only()`. Replaced agent_chat inner flow. Removed phantom-update corrector from `_ava_auto_respond`. Swapped AGENT_SYSTEM_PROMPT_BASE. Removed AGENT_TOOL_SCHEMA append. Added encoding header. |
| `tests/test_conversation_fixture.py` | 15-conversation accuracy fixture, mocks `call_llm_with_tools` |
| `tests/test_native_tools.py` | Unit tests for `call_llm_with_tools` |
| `tests/test_schema_coverage.py` | Coverage assertion: every execute_tool branch must have a schema entry |
| `docs/deletion_ticket_parse_tool_calls.md` | Tracks eventual removal of `_parse_tool_calls` |

## Pitfalls Encountered

1. **Route decorator misplacement** — `@app.post("/api/agent/chat/{tenant_id}")` landed on `_run_observe_loop` instead of `agent_chat` during insertion. Fix: verify decorator placement after inserting functions.
2. **Import in observe_loop function** — Local imports of `call_llm_with_tools` failed in test because `@patch` decorator patched the module-level reference. Fix: use `import induction_engine as _ie` and `_ie.call_llm_with_tools(...)`.
3. **ToolResult.from_string doesn't exist** — Wrong method name. Fix: use `from_legacy_string(tn, r)` from `tool_results` module.
4. **Em dashes in Python source** — `AGENT_TOOL_SCHEMA` had em dashes (U+2014) that caused SyntaxError on Python 3.14. Fix: replace with ASCII `--` or delete the constant.
5. **Doubled triple-quotes** — Prompt replacement left `""""""` (6 quotes) where old and new closing delimiters overlapped. Fix: one-line replace.
6. **Schema coverage test must be maintained** — Every new tool added to `execute_tool()` must also be added to `TOOL_SCHEMAS` in server.py, or the test fails.

## Post-Deployment Bug Fixes (June 13, 2026)

### Bug #2 — Stale Variable Names in DB Storage + Logging

**Symptom:** The `[PENDING — Reply 'send it']` marker never gets persisted. Logging silently falls through to bare `except`.

**Root cause:** The DB storage and logging sections in `agent_chat` still referenced the old single-pass variables (`db_response`, `_results`, `_tools_to_run`, `_intent`, `_is_confirmed`) which don't exist in the new observe-loop architecture. The `'db_response' in dir()` guard masked the bug — it always evaluated `False`, so `response` was used instead of `response_original`.

**Fix:** Unpack the observe loop's return dict explicitly and update ALL downstream references:

```python
_loop_out = _run_observe_loop(messages, ...)
_all_calls = _loop_out.get("all_calls", [])
_all_results = _loop_out.get("all_results", [])
response_original = _loop_out["db_response"]
_obs_intent = _loop_out.get("intent")
_obs_executed = _loop_out.get("executed", False)
```

Then use `response_original`, `_all_calls`, `_all_results` throughout — never the old names.

### Bug #3 — Pending-Action Confirmation Never Consumed

**Symptom:** User says "send it" to confirm a proposed action, but the agent starts a fresh observe loop with no memory of the parked tool call.

**Root cause:** The observe loop writes to `_pending_actions[pending_key]` on `[ACTION: ASK]`, but there was no code in `agent_chat` that checks `_pending_actions` when a confirmation message arrives on the next turn. The pending dict was written and never read.

**Fix:** Add a confirmation-resume block at the top of `agent_chat`, BEFORE message building:

```python
_confirm_words = {"yes", "send it", "send", "go ahead", "do it", ...}
if _is_confirm and _pending_actions:
    _recent_pending = find_recent_pending(tenant_id)
    if _recent_pending:
        _pending_results = [execute_tool(pc["tool"], pc["args"], ...)
                           for pc in _recent_pending["tool_calls"]]
        _resp_text = render_results(_pending_results, channel="whatsapp")
        # Store to DB, clean up pending, return directly
```

### Bug #4 — fallback_count Post-Loop Scope

**Symptom:** `fallback_count` reads `tool_calls` after the loop exits — but `tool_calls` is loop-scoped and may be the last iteration's value, not "did we use fallback anywhere."

**Fix:** Track a `fallback_fired` integer inside the loop, increment it when legacy fallback triggers, and return it from the loop output.

### System Prompt Final Swap — user_name/owner_name Split

The final behavioral prompt (committed after the Parts 0-7 build spec was complete) introduced a `user_name` vs `owner_name` distinction:

| Placeholder | Source | Role |
|------------|--------|------|
| `{agent_name}` | `ctx["agent_name"]` | The AI (Ava) |
| `{user_name}` | `ctx["owner_name"]` | Person being coached in this session |
| `{owner_name}` | `ctx["owner_name"]` | Admin — owns settings, induction, system config |
| `{company}` | `ctx["company"]` | The company (Hunar.ai) |
| `{current_datetime}` | `now_ist.strftime(...)` | "Saturday, June 13, 2026 at 11:42 AM" |
| `{timezone}` | `"IST"` | Always IST |

The pipeline context is now injected as a separate f-string append (NOT in the base prompt), keeping the base prompt stable across tenants and DB states.

## Verification

After deployment:
- `POST /api/agent/chat/{tenant_id}` with "what time is it" → verify short, direct answer (no lead suggestions)
- Check journalctl for observe_loop log lines with `native_used: True`
- Run `pytest tests/` — expect 276/276 pass (1 pre-existing failure was fixed: `test_trigger_cadence_rejects_archived`)
