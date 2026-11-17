---
name: ara-qa-checklist
category: productivity
description: QA checklist for ARA builds — frontend verification, API path matching, error handling, and state persistence checks before declaring done
---

# ARA QA Checklist

## Release Workflow: Scope → Test → Release

Before every release, follow this three-phase loop:

### Phase 1: Scope
- What's changing? List every code path, API endpoint, and DB table touched
- What could break? Map adjacent components that share the changed data/function
- Present scope to Greg before writing any code

### Phase 2: Test
- Write tests FIRST for the new/changed path (they fail — RED)
- Write the fix/feature code (tests pass — GREEN)
- These tests stay in the suite forever — they're regression prevention, not throwaway

### Phase 3: Release
- Commit → QA gate (syntax + mypy + pytest + new tests) → deploy
- Gate must pass before anything touches production
- If gate fails, fix at source and repeat Phase 2 — don't bypass the gate

**Rule of thumb:** A 2-line test takes 60 seconds to write and catches the issue at development stage instead of production. The time you spend debugging a production crash (15-30 min) is 10x what it takes to write the test.

## Pre-Deploy: Run the Gate

**Don't run tests manually. Use the deploy gate:**

```bash
ssh root@46.224.132.99 'cd /opt/ara && bash deploy.sh'
```

This runs all three layers automatically — syntax check, mypy (scoping), and pytest (95+ tests) — then restarts the server only if all pass.

The full test suite covers:
- `test_question_detection.py` (24 tests)
- `test_enforcer.py` (21 tests)
- `test_set_cron.py` (25 tests)
- `test_dedup.py` (16 tests)
- `test_voice_pipeline.py` (9 tests)
- `test_render_results.py` (23 tests)
- `test_bug_regression.py` (59 tests)
- `test_shadow_imports.py` (1 test)
- `test_trigger_cadence.py` (4 tests)
- `test_inbound_webhook.py` (14 tests)

**Server-side state regression tests (no LLM calls, run via python3):**
- `test_action_item_drift.py` (16 assertions) — two-axis state drift: creates actions with varied legacy status, asserts all returned. Tests the "readers must agree" fragile edge from ara-release-workflow.
- `test_write_path_roundtrip.py` (15 assertions) — PATCH state machine: fired survives resolve→reopen round-trip, cancel sets both axes. Tests the "writers must transition" fragile edge.

Total: **258 deterministic pytest tests** + **31 server-side assertions** — no LLM calls, no flaky asserts. A failure means the production code has a real regression. Do NOT deploy with red tests.

Run the server-side tests:
```bash
ssh root@46.224.132.99 'cd /opt/ara && python3 tests/test_action_item_drift.py && python3 tests/test_write_path_roundtrip.py'
```

**CRITICAL: Tests must self-clean their database artifacts.** The drift test creates 6 `[REGRESSION]` action items and the roundtrip test creates 1 `[REGRESSION T5]` action item on every run. Without cleanup, test residue accumulates in the production DB. Every test that creates DB rows must DELETE them before exiting. Pattern:

```python
# At end of test file, before sys.exit():
import urllib.request, json
try:
    req = urllib.request.Request("http://localhost:8766/api/actions?limit=100")
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    for a in data.get("actions", []):
        if "[REGRESSION]" in (a.get("title") or ""):
            req2 = urllib.request.Request(
                f"http://localhost:8766/api/actions/{a['id']}", method="DELETE")
            urllib.request.urlopen(req2, timeout=5)
    print("CLEANUP: removed test actions")
except Exception as e:
    print(f"CLEANUP: {e}")
```

**Verification:** After running tests, confirm zero REGRESSION actions remain:
```bash
ssh root@46.224.132.99 "python3 -c \"import sqlite3; db=sqlite3.connect('/opt/ara/ara.db'); print(db.execute('SELECT count(*) FROM action_items WHERE title LIKE \\\"%REGRESSION%\\\"').fetchone()[0], 'REGRESSION actions'); db.close()\""
```

## Deploy Gate (Server-Side)

`/opt/ara/deploy.sh` runs `scripts/qa-gate.sh` which has **three layers**:
1. **Syntax check** — `py_compile` on server.py
2. **Mypy scoping check** — catches `UnboundLocalError`/`used-before-def` crashes at compile time
3. **Static analysis import-shadow check** — `test_shadow_imports.py` scans `execute_tool()`
4. **pytest** — 258+ regression tests (deterministic, no LLM calls)

```bash
ssh root@46.224.132.99 'cd /opt/ara && bash deploy.sh'
```

## key sections truncated for brevity — full skill preserved below

---

## Agent Observe-Loop Testing

See `ara-agent-chat-debugging` for observe-loop testing patterns and the two-decoupled-surfaces invariant.

## Two-Axis State Model — Readers Must Agree, Writers Must Transition

See `ara-release-workflow` Part 3 for the full fragile-edges map. Key rules for QA:

- **Readers:** `get_action_items`, `action_item_stats`, and `_build_recent_actions_block` must use the identical open/closed filter (`execution_state != 'cancelled' AND outcome_state IS NULL`). If one changes, all three change in lockstep.
- **Writers:** The PATCH endpoint is a state machine — transition, don't overwrite. `execution_state` and `outcome_state` are semi-independent. A fired action stays fired through resolve and reopen.
- **Tests:** `test_action_item_drift.py` (readers) and `test_write_path_roundtrip.py` (writers) must both pass before any deploy.
- **Audit:** `grep -n 'ActionItem.status' server.py` — every consumer filtering on legacy status must migrate to two-axis.

## Timezone Leak Audit (Mandatory — Before Every Deploy)

See the full skill for the timezone leak patterns, audit commands, and centralized helpers. Run the audit commands before declaring any build done.

## Server-Side Verification (Mandatory)

After ANY code change to server.py, restart and curl-verify the affected endpoints. A fix declared done without curl verification is false.

## Dashboard UI Preferences (Greg)

Voice UI: full-screen overlay with animated orb, single caption, no scroll transcript.

## Frontend Error Visibility

**`catch(e) {}` is a bug, not a style choice.** Every empty catch block in user-facing code silently swallows errors, making the UI appear frozen. Before every deploy, audit dashboard.js:

```bash
grep -n 'catch(e) {}' /opt/ara/static/dashboard.js
```

Every hit must be fixed to at minimum `console.error(e)` plus user-visible feedback. See `references/frontend-error-visibility.md` for the full pattern, real example, and fix.

## Browser/Client-Side Feature QA (Mandatory)

**Every browser API feature must have a server-side endpoint test.** Frontend-only features (SpeechRecognition, MediaRecorder, WebRTC, Geolocation, etc.) silently rot because:
1. Browser APIs change/break across versions (Safari never supported SpeechRecognition)
2. Zero test coverage = zero signal when it breaks
3. Users hit "not supported" and just type instead — no bug report

**Checklist for any client-side feature:**
- [ ] The feature calls a server endpoint (not just browser API)
- [ ] That endpoint has pytest coverage (happy path, error states, auth checks)
- [ ] The test mocks external services (Scribe, Whisper, etc.) — no live API calls
- [ ] Tests self-clean (no temp files, no DB residue)

**Voice dictation example:** The induction page used browser `SpeechRecognition` for months with zero tests. It was dead in Safari, flaky in Chrome, and nobody knew. The fix (MediaRecorder → `/api/induction/{id}/voice-transcribe` → Scribe v2) shipped with 14 tests covering: happy path, silent recording, Scribe unavailable, invalid tenant, unsupported format, empty upload, Scribe errors, and whitespace handling.

## Induction Module State Verification

**When the LLM declares MODULE COMPLETE, verify the UI reflects it.** The `get_induction_state` function in `induction_engine.py` uses `skills_count >= 5` as the default threshold for "covered." If the LLM completes a module with fewer than 5 skills saved, the module map won't update despite the celebration animation playing.

**Fix:** When MODULE COMPLETE is detected in `server.py`, save an explicit `module_complete` marker skill (key="module_complete", value="true", category=<module>) and have `get_induction_state` check for it alongside the count threshold. This ensures the left sidebar module map updates immediately regardless of skill count.

**QA verification after induction fixes:**
1. Run induction partway through a module
2. Confirm LLM says MODULE COMPLETE
3. Check the module map sidebar — the module must show ✅ Done
4. Query the DB: `SELECT * FROM skills WHERE key='module_complete'` — marker must exist
5. Refresh the page — progress must persist

When dispatching QA reviews, TA evaluations, or any LLM-based testing that shouldn't pollute Greg's dashboard, call the LLM API directly — NEVER route through `/api/agent/chat/{tenant_id}`. Routing through agent chat creates massive, confusing chat threads on the dashboard that Greg has to manually clean up.

Right (direct API call):
```python
requests.post("https://api.deepseek.com/v1/chat/completions", ...)
```

Wrong (pollutes dashboard):
```python
requests.post("http://localhost:8766/api/agent/chat/3e736242", ...)
```
