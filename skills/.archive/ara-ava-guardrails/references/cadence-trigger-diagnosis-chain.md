# Cadence Trigger Diagnosis Chain

When "start an outbound sequence" fails, there are **4 independent layers** that can block it. Check them in order.

## Layer 1: Python Scoping Crash

**Symptom:** `UnboundLocalError: cannot access local variable 'ScheduledAction' where it is not associated with a value`

**Cause:** `from database import ScheduledAction` (no alias) inside `execute_tool()` shadows the module-level import. Python compiles ANY `from X import Y` in a function as a local binding for the entire function. If another code path in the same function references the name BEFORE the import line, it hits `UnboundLocalError`.

**Fix:** Every `from X import Y` inside `execute_tool()` must use `as _Alias`. Run `tests/test_shadow_imports.py` (static analysis, 0.02s) to verify.

**Verification:** `curl -X POST http://localhost:8766/api/cadence/trigger/lead/{lead_id}` returns results (not crash).

## Layer 2: Model Routing — Wrong LLM (HISTORICAL — FIXED June 13, 2026)

**Status:** This layer is now **obsolete**. The keyword-based model router was deleted entirely. The agent loop now uses `deepseek-v4-pro` unconditionally. No routing decision means no wrong LLM can be selected.

**Historical symptom (pre-June 13):** No crash, but Ava says "I tried to start the outbound cadence but the system hit an internal error" — a conversational deflection, not a tool call.

**Root cause:** The `_model_routing_keywords` set didn't include `start`, `outbound`, `sequence`, or `cadence`. The request routed to DeepSeek V4 Flash, which fabricated the "internal error" message instead of calling `trigger_cadence`.

**Fix (at the time):** Expand the keyword set. **Now superseded by:** `_chat_model = "deepseek-v4-pro"` (no routing).

## Layer 3: Approval Workflow — Pending Confirmation

**Symptom:** Ava drafts the tool call and shows `[PENDING]` but the user thinks it's already executing. The user says "Has it started?" — no tool was ever called.

**Root cause:** The LLM writes "Starting... now" (assertive language) but the system stores the tool call as pending. The user reads the message, not the `[PENDING]` label.

**Fix (two parts):**
1. **Prompt:** `[ACTION: ASK]` instruction tells LLM to write proposals as questions ("Shall I...?" / "I can... want me to?")
2. **DB message:** Prefix changed from `[PENDING - awaiting your confirmation]` to `[PENDING - Reply 'send it' or 'confirm' to proceed]`

**Verification:** Ask Ava to start a cadence. The message should read as a question, not an assertion.

## Layer 4: Status Questions — read_logs Spiral

**Symptom:** User asks "Has it started?" → Ava says "Let me check the logs" → silent indeterminate wait → no useful answer.

**Root cause:** `read_logs` was listed under "Read-only tools (call freely without asking)" and the Error Handling section primed the LLM to use it as a first-line diagnostic. The LLM never looked at the conversation history where the pending proposal was visible.

**Fix:** 
- Remove `read_logs` from the free-call list
- Add "Answering Status Questions From Context" prompt section with explicit instruction to read conversation history first
- `read_logs` is now ONLY for recovery after a tool call fails with an unclear error

**Verification:** Ask "Has it started?" when a pending action exists. Ava should say "It's still pending awaiting your confirmation" — not "Let me check the logs."

## Layer 5: No Published Cadence Config

**Symptom:** Tool call succeeds (returns "Started cadence: 0 steps") but no scheduled actions appear.

**Root cause:** No published template exists for the cadence type. The `_schedule_cadence_for_lead()` function queries `CadenceConfig` by `template_id` and finds nothing.

**Fix:** Publish the cadence template via the Cadence Builder UI or API:
```
POST /api/cadence/publish
{"template_id": "cold", "template": {"steps": [...], "promptParts": {...}}}
```

**Verification:** `GET /api/cadence/config/cold` returns the config. `curl -X POST /api/cadence/trigger/lead/{id}` returns `scheduled > 0`.

## Layer 6: Publish Button Shows "Unknown Error"

**Symptom:** User clicks Publish, gets "❌ Publish failed: Unknown error" — but the backend actually succeeded.

**Root cause:** Frontend checks `data.status === 'ok'` but backend returns `{"status": "updated"}` or `{"status": "created"}`. The string `"updated" !== "ok"`, so it falls through to the error branch.

**Fix:** Change frontend check to `if (data.status)` (truthy). Same fix needed in both `cadence_template.py` (main publish) and `prompt_builder_template.py` (prompt builder publish, which also has a validation check that uses `data.status === 'ok'` instead of `data.valid`).

**Verification:** Click Publish → green "published" toast appears.

## TL;DR — Quick Diagnosis by Symptom

| Symptom | Check |
|---------|-------|
| `UnboundLocalError` crash | Layer 1 |
| "internal error" without a crash | Layer 2 — check `Model routing:` log line |
| `[PENDING]` draft shown but never executes | Layer 3 |
| "Let me check the logs" on status questions | Layer 4 |
| Tool succeeds but "0 steps scheduled" | Layer 5 |
| "Unknown error" on Publish button | Layer 6 |
