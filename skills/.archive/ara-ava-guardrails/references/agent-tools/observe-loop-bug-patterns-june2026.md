# Observe-Loop Bug Patterns (June 2026 Technical Advisor Review)

The technical advisor reviewed the native function calling implementation and
found four bugs. These patterns recur across any observe-loop or tool-calling
refactor — capture them to short-circuit future reviews.

## Bug #1: Route Decorator on Wrong Function

**Symptom:** FastAPI endpoint returns `{"detail": [{"type": "missing", "loc": ["query", "messages"], ...}]}` or the endpoint is dead (no route registered).

**Root cause:** The `@app.post(...)` decorator in a Python file binds to the **next function defined**, not the nearest function above it. When helper functions (observe loop, claim check) are defined between the decorator and the intended endpoint function, the decorator attaches to the wrong one.

**The code:**
```python
# WRONG — decorator binds to _run_observe_loop, agent_chat has no route
@app.post("/api/agent/chat/{tenant_id}")

def _run_observe_loop(messages, tools_schema, db, wa, tenant_id, user_msg, channel):
    ...

def agent_chat(tenant_id: str, data: dict, db: DBSession = Depends(get_db)):
    ...

```

**Fix:** Place helper functions BEFORE the decorator, or place the decorator directly above the endpoint function:

```python
# CORRECT — helpers above, decorator right above agent_chat
def _run_observe_loop(messages, tools_schema, db, wa, tenant_id, user_msg, channel):
    ...

def _claims_action_without_call(text):
    ...

@app.post("/api/agent/chat/{tenant_id}")
def agent_chat(tenant_id: str, data: dict, db: DBSession = Depends(get_db)):
    ...
```

**Verification:** grep for `@.*post.*agent.chat` and confirm the decorator sits directly above `def agent_chat(`.

## Bug #2: Stale Variable Names After Refactoring

**Symptom:** Structured logging silently produces empty data. Pending confirmation markers not persisted. The code runs without crashing but the output is wrong.

**Root cause:** After refactoring the inner agent loop, the DB storage and logging sections still reference old variable names from the deleted architecture. Python's `'var' in dir()` guard masks the bug — it silently falls back to defaults.

**Pattern to check after any refactor that changes variable scoping:**

| Old variable (deleted) | New variable (from observe loop output) |
|------------------------|----------------------------------------|
| `_results` | `_all_results` |
| `_tools_to_run` | `_all_calls` |
| `db_response` | `response_original` (`_loop_out["db_response"]`) |
| `_intent` | `_obs_intent` |
| `_is_confirmed` | `_obs_executed` |
| `response_clean` | N/A — removed in observe loop design |

**Fix:** Search for ALL old variable references in the DB storage and logging sections, not just the ones you just changed. Apply a systematic sweep:

```bash
grep -n '_results\|_tools_to_run\|_intent\|_is_confirmed\|db_response' server.py
```

**Verification:** Check that the logging section uses the exact same variable names as the observe loop return dict. Every `_loop_out[key]` must have a corresponding local variable that the logging section reads.

## Bug #3: Pending-Action Written But Never Consumed

**Symptom:** When the user says "send it" / "go ahead" / "yes", the observe loop starts a fresh run with no memory of the parked tool calls. The pending dict (`_pending_actions`) gets written but never read — the confirmation is lost.

**Root cause:** The confirmation-resume logic (checking `_pending_actions` at the top of the turn) was dropped during the refactor. The observe loop wrote the pending state but `agent_chat` never checked for it on the next message.

**Fix:** Add a pending-confirmation resume block at the top of `agent_chat`:

```python
# Before message building, check if the user is confirming a pending action
_confirm_words = {"yes", "send it", "send", "go ahead", "do it", "confirm", "proceed"}
_lower_msg = user_msg.strip().lower()
if _lower_msg in _confirm_words and _pending_actions:
    # Find most recent pending action for this tenant
    _recent = sorted(
        [(k, v) for k, v in _pending_actions.items() if k.endswith(f"_{tenant_id}")],
        key=lambda x: x[1].get("timestamp", 0), reverse=True
    )
    if _recent:
        _pending_calls = _recent[0][1].get("tool_calls", [])
        # Execute pending tools, render, store to DB, return
        ...
        del _pending_actions[_recent[0][0]]
        return {"response": _resp_text, ...}
```

**Key requirements:**
- The pending dict key must include the tenant_id so filtering by tenant is reliable
- Execute the parked tool calls with the `[ACTION: NOW]` intent (no re-confirmation)
- Clean up the pending entry after execution to prevent stale confirmations

## Bug #4: Post-Loop Variable Scope Reads Wrong Value

**Symptom:** `fallback_count` reports incorrect statistics — says 0 when fallbacks were used, or higher than actual.

**Root cause:** The `fallback_count` expression reads `tool_calls` after the observe loop exits. But `tool_calls` is a loop-scoped variable that gets rebound on each iteration. After `MAX_TOOL_STEPS` or a `break`, `tool_calls` holds the **last iteration's** value — not a cumulative count.

**Fix:** Track the metric as a dedicated variable inside the loop:

```python
fallback_fired = 0  # declare before the loop

# Inside the loop, when fallback is used:
fallback_fired += 1

# In the return dict:
"fallback_count": fallback_fired,
```

**Verification:** Send a request that triggers legacy fallback (`[TOOL_CALL:]` text markers). Check the structured log — confirm `fallback_count > 0`.

## General Lessons

1. **When inserting new functions between an existing decorator and endpoint, always re-check decorator binding.** The compiler doesn't warn you.

2. **After refactoring a function's inner flow, grep for ALL old variable names in the enclosing file.** The `dir()` guard pattern (`'var' in dir()`) is a smell that masks silent failures — fix it to use actual variable references.

3. **State machines (pending → confirm → execute) need end-to-end tracing.** Verify that every "write" point has a corresponding "read/handle" point. A pending write with no consumer is dead code.

4. **Metrics that read loop-scoped variables after loop exit are unreliable.** Track them as dedicated accumulators that persist across iterations.
