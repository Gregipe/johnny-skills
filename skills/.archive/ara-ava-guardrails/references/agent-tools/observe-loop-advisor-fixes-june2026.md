# Observe Loop — Advisor Review Fixes (June 13, 2026)

Four bugs caught by the technical advisor after the initial implementation of Parts 1-7.

## Bug #1: Route Decorator on Wrong Function

**Problem:** `@app.post("/api/agent/chat/{tenant_id}")` was visually above `agent_chat` but
bound to `_run_observe_loop` (the function defined next in the file). FastAPI then tried to
route POST requests into a helper with no valid endpoint signature.

**Fix:** Move the decorator to sit directly above `def agent_chat(...)`. Keep helper functions
(decorator-less) above the route handler.

## Bug #2: Stale Variable Names in Caller

**Problem:** After extracting `_loop_out = _run_observe_loop(...)`, the DB storage and logging
sections still referenced old single-pass variable names:
- `db_response` → should be `response_original` (unpacked from `_loop_out["db_response"]`)
- `_results`, `_tools_to_run` → should be `_all_results`, `_all_calls`
- `_intent`, `_is_confirmed` → should be `_obs_intent`, `_obs_executed`

The `'db_response' in dir()` guard masked the bug — it silently fell through to `response`
every time, so `[PENDING]` markers in `db_response` were never persisted.

**Fix:** Unpack ALL return dict keys explicitly after the helper call. Search for old variable
names using `grep -n` and replace every reference.

## Bug #3: Pending-Action Confirmation Never Consumed

**Problem:** The observe loop writes pending tool calls to `_pending_actions[pending_key]` on
`[ACTION: ASK]`, but the next turn ("send it", "go ahead") triggered a fresh `agent_chat`
with no memory of the parked tool calls.

**Fix:** Add a confirmation-resume block at the top of `agent_chat` (before message building)
that detects confirmation response patterns and executes the most recent pending tool calls
directly — bypassing the LLM entirely.

## Bug #4: `fallback_count` Reads `tool_calls` After Loop Scope

**Problem:** The `fallback_count` calculation at the bottom of `_run_observe_loop` read
`tool_calls`, which was scoped inside the `while steps < MAX_TOOL_STEPS` loop. On the
broken-via-`final_text` path, `tool_calls` was `[]` (fine), but on the
broken-via-`claims_action` path it read the *last iteration's* value — not "did we use
fallback anywhere."

**Fix:** Track `fallback_fired = 0` before the loop, increment inside the legacy fallback
branch, and output `fallback_fired` in the return dict.

## Also Fixed: `ToolResult.from_string` → `from_legacy_string`

Two places used the non-existent `ToolResult.from_string` method instead of the correct
`from_legacy_string` function (imported at the top of `server.py`). Found in:
1. The observe loop's `tr = r if isinstance(r, ToolResult) else ...`
2. The pending-action resume block's result wrapping
