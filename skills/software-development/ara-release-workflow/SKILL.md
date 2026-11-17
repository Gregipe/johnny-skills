---
name: ara-release-workflow
description: ARA release workflow — implementer working agreement, fragile-edges map, and test suite run order. Load before any ARA code change.
---

# ARA Release Workflow — Implementer Working Agreement & Fragile-Edges Map

## Part 1 — Non-negotiable workflow

1. **State blast radius before editing.** List every consumer of what you're changing: functions that call it, code paths that read the field, outputs that render it. Write it out. If you can't name the consumers, go read first. Consult Part 3 for known couplings.

2. **One logical change per task.** No bundling. No "also improve" adjacent code. No reformatting/renaming/cleanup unless the task requires it. Call out and justify any unrequested diff.

3. **Run the FULL existing suite before declaring done.** `full_regression.py`, `verify_battery.py`, and relevant `gate_*.py` must all be green. A green new feature with one red pre-existing test is a failed task.

4. **Never weaken an existing test to make your change pass.** Add tests, don't edit/loosen/delete passing ones. If an existing test must change because behavior legitimately changed, STOP and flag for explicit human sign-off.

5. **Every bug fix adds a test that would have caught it.** The test is part of the fix, not a follow-up.

6. **Manual render check on user-facing output.** If your change touches strings/emojis/formatting the user sees, produce the actual rendered output for human eyeball. Assertions don't see formatting.

7. **Delete tests when their target is deleted.** When a function, class, or code path is deliberately removed, its tests become dead noise. Delete them in the same commit. Dead tests always fail and train the agent to ignore red — 20 always-red tests drowns 1 new red test, exactly how real regressions slip through. This session proved it: 20 dead `_claims_action_without_call` tests camouflaged the S3 crash and synthesis behavior gap. Check after any deletion: `grep -rn '<deleted_function>' tests/` — if hits remain, delete them.

8. **Tests that create data MUST self-clean.** Any test that creates records (ActionItems, ScheduledActions, etc.) must delete them before exiting. Test residue in the production database is unacceptable — Greg sees it on the dashboard. Add a cleanup block before `sys.exit(0)` in every test file:
```python
# ── CLEANUP ──
import urllib.request, json
try:
    req = urllib.request.Request("http://localhost:8766/api/actions?limit=100")
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    for a in data.get("actions", []):
        if "[REGRESSION]" in (a.get("title") or ""):
            urllib.request.urlopen(urllib.request.Request(
                f"http://localhost:8766/api/actions/{a['id']}", method="DELETE"), timeout=5)
except Exception: pass
```
Verify after every test run: `SELECT count(*) FROM action_items WHERE title LIKE '%REGRESSION%'` must return 0.

8. **A crash that prevents assertions from running is a FAILURE, not a skip.** A 500 Internal Server Error or JSON decode crash in the test harness means an unknown number of assertions never executed. Do not report remaining assertions not reached as neutral — they count as untested. The crash IS the failure. Fix it first, then re-run the full suite. See references/datetime-naive-aware-crash.md for the most common crash pattern in this codebase.

9. **Never relabel regressions as pre-existing to produce a green verdict.** When a test fails after a change and you assess it as pre-existing, flaky, or test harness issue, verify that claim with evidence — check git blame, re-run the test on the parent commit, or confirm the code under test has not been touched. A report where 100% of failures are assessed as not from today's changes is statistically implausible and should be distrusted by default. If 29 tests fail and zero are attributed to your changes, the explanation is the thing to distrust, not the lights. The suite exists to tell you bad news — a green verdict laid over red evidence is worse than no suite. This session: S3 crash dismissed as harness issue, synthesis G1.r2 labeled pre-existing not yet implemented when a77e6d8 was deployed and working. Both were real; both were explained away.

10. **Verify diagnosis cheaply before fixing — don't fix a theory.** Before touching any code, run a cheap probe against the live system (SQL query, curl, log grep) to confirm the bug matches your theory. Greg's pattern: "First — verify the diagnosis cheaply, so you're not fixing a theory. Run the query by hand against the DB. If you see X, that's the bug confirmed in one look." Fixing code without confirming the diagnosis first wastes cycles and risks introducing regressions for a bug that isn't actually present. This session: the status/outcome_state drift theory was disproven by a 1-second SQL query — the DB was clean, the real issue was LLM context collapse. If we'd fixed the endpoint first, we'd have "fixed" a non-bug and missed the actual problem.

11. **Validate build plan line numbers against production before implementing.** When a build plan references specific line numbers in `server.py` (e.g., "add check at ~line 6493"), SSH to production and verify: (a) the file still has the expected line count, (b) the target line numbers still point to the code the plan assumes, and (c) any proposed new functions/constants don't already exist. server.py is 12,690+ lines and drifts across deploys — a plan written against last week's code may reference wrong locations. Verify with `wc -l`, `sed -n`, and `grep -n` before touching any code. A plan audited against wrong line numbers produces wrong changes.

12. **Verify code patterns match production, not the plan's assumptions.** A build plan may reference code patterns (e.g., `ToolResult` objects, `ToolResult.success()`) that don't match the actual production code (which may use legacy string returns for the same path). Before applying any plan-sourced patch, read the actual code at the target location — never trust the plan's code snippets as verbatim. Adapt patches to match the actual code style. This session: the plan assumed `ToolResult.success()` for send_whatsapp, but production uses raw `return f"WhatsApp sent to..."` strings.

13. **After `systemctl kill`, verify the old process has EXITED before starting.** The ARA server's graceful shutdown can take 22+ seconds when in-flight LLM requests are pending. `systemctl kill` sends SIGTERM and returns immediately — the process continues running. If you `systemctl start` before the old process dies, port 8766 is still held → EADDRINUSE → new process fails silently. `systemctl is-active` reports "active" because the old process is still alive, but it dies seconds later. Verify: `while systemctl is-active ara-server --quiet 2>/dev/null; do sleep 2; done` before starting. Or use `systemctl restart` which handles the wait correctly.

14. **Variables initialized inside `if not pre_confirmed:` are UNDEFINED on the pre_confirmed path.** The confirmation flow has two paths: normal (gate → classifier → observe loop) and pre_confirmed (skip gate, straight to observe loop via `[ACTION: NOW]`). Any variable initialized inside `if not data.get("pre_confirmed", False):` block will be `UnboundLocalError` when referenced later and the pre_confirmed path was taken. Initialize such variables BEFORE the gate at a scope both paths can reach. This session: `_entity_guard_text` was defined inside the block but referenced at message construction (line 7489), crashing every `[ACTION: NOW]` execution.

15. **Echo-detection content-match is TOO AGGRESSIVE — single words can match assistant text.** `_is_echo_message()` has two checks: prefix regex (✨ Ava :, Forwarded:) and content-match against recent assistant messages. The content-match does `stripped[:100] in assistant_content` — which means ANY short user word that appears in the assistant's confirmation prompt triggers the echo gate. Example: assistant says "⏳ Waiting for you — reply **yes** to confirm or no to cancel", user types "yes" → content-match finds "yes" in the assistant text → echo-detected → `_live = None` → pending action is never consumed → infinite confirmation loop. The echo branch also silences the detection — no feedback to the user, just a repeated confirmation prompt. **Deployed fix (commit `4afe801`):** Two root causes. (a) Content-match minimum length: `if len(stripped) >= 40:` before the content-match check — real copy-pastes are 40+ chars. Single-word confirmations ("yes", "ok", "no", "sure") never trigger content-match. (b) Classifier output hardening: `_classify_confirmation()` was returning `"confirm.\n"` from the LLM, which failed raw string compare → defaulted to "unrelated" → `verdict=None`. Fix: extract first token, strip punctuation before validation — `token = (raw or "").strip().lower().split()[:1]; token = token[0].strip(".,!?:;\"'")`. See `references/echo-gate-infinite-confirmation-loop.md` for the full log trace, both root causes, and verification proof.

## Part 2 — Definition of done

All five must be true:
- Blast radius stated and checked
- Diff minimal, extra changes justified
- Full suite green (no pre-existing red; dead tests deleted)
- Test covering the fix added
- User-facing output rendered (where applicable)

## Part 3 — Fragile-edges map (load-bearing couplings)

### db_response vs response
Two different strings. `response` = rendered/observe-loop text. `db_response` = what persists and what voice/WhatsApp handler sends. Voice handler MUST read `db_response` (the [PENDING] prompt), not bare `response`. Consumers: agent_chat return, whatsapp_voice_inbound, coaching WhatsApp send path, DB persistence.

### One confirmation gate (agent_chat) — WhatsApp path delegates via HTTP

**Verified June 29, 2026:** The confirmation gate lives ONLY in `agent_chat` (server.py ~line 7006). The WhatsApp coaching path (`_handle_owner_coach_whatsapp`, line 11522) does NOT have its own confirmation logic — it prunes stale rows then POSTs to `agent_chat` via HTTP (line 11636: `requests.post("http://localhost:8766/api/agent/chat/{TENANT_ID}", ...)`). So a change to confirmation logic in `agent_chat` automatically covers both dashboard and WhatsApp paths.

**Historical note:** An older version of this skill said "two confirmation gates — MUST check BOTH." That was true when `_handle_owner_coach_whatsapp` had its own inline keyword/regex confirmation matching. That code was removed; the coaching path now delegates entirely to `agent_chat`. Do NOT reintroduce a second confirmation gate in the WhatsApp path — it will drift from the `agent_chat` gate.

**What still MUST be checked:** The `_handle_owner_coach_whatsapp` path calls `_prune_pending_actions(db, TENANT_ID)` at line 11576 before forwarding. Any change to prune logic affects both paths.

### Tiered context injection
Three tiers inject different context. Recent-actions block appears for status and command, NOT smalltalk. Any context assembly change must verify all three tiers. Smalltalk leaking the actions block has regressed before. Check: tier branch AND block injection that follows.

### Pending action store = ActionItem (not old dict)
Pending confirmations persist as ActionItem rows (`awaiting_approval` + `pending_tool_calls`), restart-safe. Do NOT reintroduce in-memory dict. Check: `_prune_pending_actions`, `_live_pending_for_tenant`, confirm execution path.

### Synthesis pass gated to write-turns only
Read-only/status/smalltalk turns must NOT route through tool-free synthesis. Gap-detection in synthesis is model reasoning over trace-vs-results — NOT verb/keyword scan. Do NOT add pattern-matching to detect described-but-uncalled — it expires on rephrasing (G5/"shoot a message" proves this).

**Known limitation:** The synthesis pass prevents false claims (won't say "WhatsApp sent" if send_whatsapp wasn't called) but the LLM doesn't consistently *offer* the missed action as a next step. The synthesis instruction tells it to offer ("Want me to send that WhatsApp now?"), but in practice it sometimes just narrates what WAS done without flagging what WASN'T. This is visible in `gate_synth.py` G1.r2: update_action fires, no send_whatsapp, response correctly says "Done — moved deadline" but doesn't add "Want me to send the WhatsApp?" The gap is in the synthesis prompt's instruction-following, not in the code gating. Do not treat this as a code regression — the structural prevention is working. The instruction-tuning is a separate improvement task.

### Deleted guards stay deleted
_claims_action_without_call, _action_map, _mode_reminders removed deliberately. Do NOT reintroduce mid-loop detection. Only legitimate detection lives at loop exit / in synthesis.

### Debugging direction: reason backward from the error, not forward from the changes

When investigating a test failure or crash, start from the stack trace and trace backward to the root cause — do NOT anchor on what you changed today and reason forward to what could fail. The changes-you-made anchor is a plausibility trap: it makes you suspect the scariest change (e.g. multi-step removal) while the real bug is in unrelated code shipped sessions ago (e.g. datetime sort in the recent-actions block). The stack trace beats a plausibility argument every time. This session: the advisor suspected change #4 for the S3 crash; the stack trace pointed to _build_recent_actions_block line 6347, a latent bug from two sessions ago. The stack trace was right.

### Sidecar inbox durability ordering
Write to durable inbox BEFORE forwarding. Mark processed=true only after 200. Check ALL message entry points, not just one.

### Classifiers are LLM calls, not regex
Tier classifier and confirmation classifier use LLM reasoning. Do NOT "optimize" with keyword lists — keyword versions have failed repeatedly.
### ActionItem state triplex (status, outcome_state, execution_state) must stay in sync

Three state fields on ActionItem: `status` (`open`/`resolved`/...), `outcome_state` (`resolved`/`failed`/...), `execution_state` (`pending`/`fired`/`completed`/...). When they drift (e.g. `outcome_state="resolved"` but `status="open"`), different API endpoints filter on different fields:
- `/api/activities` filters `outcome_state != "resolved"` → action still appears as active task
- `/api/leads/{id}/actions` renders all actions but shows `outcome_state` for "done" styling → action appears resolved/greyed
Result: same action looks active on ⚡ Actions page but done on lead detail page. Fix: audit with `SELECT id, title, status, outcome_state, execution_state FROM action_items WHERE outcome_state != status` — sync any drift. Also check that write paths update all three fields together — a PATCH that only sets `outcome_state` without touching `status` creates this inconsistency. Check: POST `/api/actions`, PATCH `/api/actions/{id}`, `_check_and_create_action_items`, confirm execution path.

**Drift regression test:** `tests/test_action_item_drift.py` creates 5 items with varied status values and asserts the default `/api/action-items` endpoint returns ALL of them, not just `status="open"`. The test currently FAILS (3 of 5 dropped) — proving the default filter at server.py line 7214 is too aggressive. See `references/action-item-drift-test.md` for the full bug description and reproduction. See `scripts/test_action_item_drift.py` for the re-runnable probe.

### SQLAlchemy filter traps — NULL != X is NULL, not True

SQLAlchemy filters that look correct at a glance can silently drop rows. `ActionItem.outcome_state != "resolved"` returns NULL (not True) for rows where `outcome_state IS NULL` — in SQL, NULL comparisons always yield NULL, and WHERE NULL means "exclude." Every action with `outcome=None` gets filtered out, which is almost always NOT the intent. Always use `or_(Column != value, Column == None)` when excluding a value from a nullable column. The `/api/activities` endpoint had this exact bug (Jun 2026) — adding `outcome_state != "resolved"` wiped the entire action list because most actions had outcome=None. Fix: `or_(ActionItem.outcome_state != "resolved", ActionItem.outcome_state == None)`.

### Action state drift — debug from agent_chat_messages, not just DB

When Greg reports "actions disappeared," the DB may show them as resolved — but the question is WHEN they resolved. Check `agent_chat_messages` for the last time Ava reported pending actions (e.g. Greg's WhatsApp query at 8:03 AM). Compare the reported list against current DB state. If actions were listed as pending by Ava but now show `outcome=resolved` in DB, check the `status` vs `outcome_state` fields — drift between these two (e.g. `status="open"` but `outcome_state="resolved"`) is the root cause. Ava's `get_action_items` tool reads `status`, while the fixed `/api/activities` endpoint reads `outcome_state` — same action looks active to Ava but resolved on the page. See also `references/action-state-drift-debug.md`.

### IST/UTC conversions — NEVER ad-hoc (Jun 2026)

All IST↔UTC conversions must go through the three central functions in `app/config.py`. NEVER write `- timedelta(hours=5, minutes=30)` or `- IST_OFFSET` inline — these drift, get copied incorrectly, and caused repeated 6-AM message storms.

```python
# app/config.py — single source of truth
ist_to_utc(dt)     # IST → UTC: subtracts 5:30
utc_to_ist(dt)     # UTC → IST: adds 5:30
parse_due_at(str)  # Parses ISO string, defaults date-only to 18:00, converts IST→UTC
```

**Bug classes this prevents:**
1. `create_action_item` tool skipped conversion for date-only strings (`len <= 10` guard)
2. `set_cron` tool used `utcnow().replace(hour=IST_hour)` — treated UTC clock as IST
3. 17 different ad-hoc patterns scattered across server.py, impossible to audit

**Audit command:** `grep -n 'timedelta(hours=5.*30)\|IST_OFFSET' server.py` — if it returns any hits besides the comment in config.py, you have a bug.
Multiple endpoints return the same data type (ActionItem) but serialize `due_at`/`created_at` differently. `/api/actions` and `/api/leads/{id}/actions` use `to_ist()` (returns `"2026-06-18T18:00:00+05:30"` — offset-aware, JS `new Date()` parses correctly). `/api/activities` used raw `.isoformat()` (returns `"2026-06-18T12:30:00"` — offset-naive, JS treats as local time → 5.5h off in IST). Any new endpoint that returns datetime fields MUST use `to_ist()`. Audit: `grep -n '\.isoformat()' server.py | grep -v 'to_ist\|#\|tzinfo\|utcnow'` — all remaining hits must be for DB storage/internal ops, never API responses.

### Activities API `action_` prefix vs Actions API raw ID — frontend coupling trap

The `/api/activities` endpoint returns action IDs with `action_` prefix (`"action_493719ff"`), while `/api/actions/{id}` and `/api/action-items/{id}` expect raw DB IDs (`"493719ff"`). The Actions page renders from activities data, so all `data-aid` attributes carry the prefixed ID. When the frontend edit/resolve/delete functions pass this verbatim to `/api/actions/{action_493719ff}`, it returns 404 `{"detail": "Action not found"}`. Two bugs compound: (a) the wrong ID, (b) the frontend checks `a.error` but the 404 response uses `a.detail` — so the error is silently swallowed, and the edit modal renders with `undefined` for title/description/due_date. Fix: strip `action_` prefix at the top of `editActionItem()`, `resolveActionItem()`, and `deleteActionItem()` with a shared helper. Also: check `a.detail` alongside `a.error` in the edit fetch handler.

### Modal overlays intercept native date picker events on macOS

Native `<input type="date">` and `<input type="datetime-local">` pickers render outside the DOM in a system-level popover. On macOS, clicks on the picker can propagate to the modal overlay's close-on-backdrop-click handler, preventing the picker from closing or the selected date from being committed. Fix: add `onfocus="event.stopPropagation()"` and `onclick="event.stopPropagation()"` to every date/time/datetime-local input inside a modal. Applies to both the Add Action modal and the Edit Action modal.

### Confirmation prompts must be explicit questions AND batch-execute on single confirm

Ava's `[ACTION: ASK]` confirmation prompts are user-facing output (Part 1 rule 6 applies). Greg's explicit preference: confirmation prompts MUST be a clear question ending with `?` that the user can answer yes/no to. The wrapper text must signal that this is a blocking wait step: `"⏳ Waiting for you — reply yes to confirm or no to cancel:"`. The system prompt instruction for `[ACTION: ASK]` must say "MUST be an explicit question ending with ?" and include two negative examples (not just one): "NOT 'Sending email to Jimmie Tete.' NOT 'Email ready for Jimmie Tete.'" The instruction must state that this is a BLOCKING step — nothing happens until the user replies. Check: system prompt `[ACTION: ASK]` line and the `db_response` wrapper at the confirmation-short-circuit path in `agent_chat`.

**Batch execution rule:** The multi-step confirmation path (execute one tool, keep rest queued, ask for next with "⏭ Next (2/9)") was REMOVED. When the user confirms, ALL pending tools execute in a single batch. One "yes" = all tools fire. The `_split_partial_rejection` path (user says "ignore X, just do Y") still works — handled in the reject branch. Check: `if len(_pending_calls) <= 1:` guard was removed — the confirm path now always loops over all pending calls. Never reintroduce the step-by-step confirmation loop.

### Confirmation classifier must handle status-check replies as confirm

The `_classify_confirmation` LLM call classifies user replies as `confirm`/`reject`/`unrelated`. Status-check replies that IMPLY the user expected execution count as `confirm`: "done?", "is it done?", "update?", "any update?", "what happened?", "did you do it?" — the user is asking because they expected the proposal to execute. Without this rule, each status check spawns a NEW duplicate confirmation (classifier saw it as "unrelated" and created fresh pending_confirmation rows with identical tool calls). Also add "ok", "sure", "perfect" to the explicit confirm examples. Check: `_classify_confirmation` system prompt for the status-check rule and the expanded affirmative list.

### Datetime sort keys — naive vs aware comparison crashes server (500)

`datetime.now(timezone.utc)` returns offset-aware datetime. SQLite stores datetimes as naive strings (no timezone). When Python's `sort()` compares a naive `r.created_at` from SQLite against an aware `datetime.now(timezone.utc)`, it raises `TypeError: can't compare offset-naive and offset-aware datetimes` → 500 Internal Server Error. The crash kills the test suite before assertions run and returns empty/non-JSON to curl — tests interpret this as a JSON decode error, but the root cause is the naive/aware mismatch in the sort key.

Fix: normalize all datetimes to naive before sorting by stripping tzinfo. `from datetime import datetime` required in the function.
```python
def _sort_key(r):
    dt = r.resolved_at or r.created_at
    if dt is None:
        return datetime.min
    return dt.replace(tzinfo=None) if hasattr(dt, 'tzinfo') and dt.tzinfo else dt
rows.sort(key=_sort_key, reverse=True)
```
String comparison was considered but rejected — it's fragile if timestamp formats drift, though ARA's ISO 8601 format happens to sort correctly. Normalized datetime comparison preserves proper chronological ordering regardless of format. See `references/datetime-naive-aware-crash.md`.

### Frontend form inputs requiring backend fields need defaults
`<input type="date">` has no value by default (shows mm/dd/yyyy placeholder). If the user sets time but skips the date picker, `input.value` is `""` → null in POST body. Every form with a date/time input that feeds a required DB field must pre-fill with a default (today's date) in the render function. Affected: any modal form that creates DB records with datetime columns via POST.

### Two-axis state drift — readers must agree (Jun 2026)

`get_action_items`, `action_item_stats`, and `_build_recent_actions_block` must use the **identical** open/closed filter. `execution_state`/`outcome_state` are the source of truth; legacy `status` is display convenience. If one read surface changes, all must change in lockstep.

**Correct "open" filter:** `execution_state != 'cancelled' AND outcome_state IS NULL` — copied verbatim from `_build_recent_actions_block`. Never infer state values from memory; read the block.

**Failure mode if they disagree:** badge count and board show different numbers — user cannot reconcile which is true.

**All three surfaces:**
| Surface | Location |
|---------|----------|
| `get_action_items` tool | `elif tool_name == 'get_action_items'` |
| `list_action_items` endpoint | `GET /api/action-items` |
| `action_item_stats` endpoint | `GET /api/action-items/stats` |

**Status query param mapping:** `open` → `execution_state != 'cancelled' AND outcome_state IS NULL`, `resolved` → `outcome_state == 'resolved'`, `dismissed` → `execution_state == 'cancelled'`. Verify mappings against production data before encoding — zero rows have `status='dismissed'` in production, so that path is unverified.

**Audit all consumers:** `grep -n 'ActionItem.status' server.py` — every hit that filters on legacy status for open/closed semantics must migrate to two-axis. The June 2026 audit found 7 drifted consumers beyond the three main surfaces.

### PATCH write path is a state machine — transition, don't overwrite (Jun 2026)

`execution_state` and `outcome_state` are semi-independent axes. **Each user action maps to a specific field update, never a wholesale rewrite of both axes.**

| Action | Field changes | Do NOT touch |
|--------|--------------|--------------|
| Resolve | `outcome_state='resolved'`, `resolved_at=utcnow()` | `execution_state` |
| Re-open | `outcome_state=NULL`, `resolved_at=NULL` | `execution_state` |
| Cancel | `execution_state='cancelled'`, `outcome_state='cancelled'` | — |

**Why mandatory:** a blind overwrite that resets `execution_state='pending'` on resolve **erases the record that it fired.** A fired action stays fired through resolve and reopen. If a sent WhatsApp action flips to 'pending' on resolve, the database now claims it was never sent — the same harm class as the false-claim bug, baked into persisted data.

**Test:** `tests/test_write_path_roundtrip.py` — creates a fired action, resolves it (asserts `execution_state` still 'fired'), reopens it (asserts `execution_state` STILL 'fired'). The execution fact must survive the round trip.

**Constraint boundary:** do NOT backfill historical rows. Old data stays as-is. But new writes through the PATCH endpoint MUST populate both axes.

## Part 4 — Suite run order

Every time, in sequence:
1. `tests/gate_synth.py` (synthesis pass, 13 assertions)
2. `tests/gate_retry.py` (retry logic, 7 assertions)
3. `tests/full_battery.py` (broad sweep, 61 assertions)
4. Any new test added

Run them SEQUENTIALLY with generous timeouts (each does live LLM calls). Parallel runs cause DeepSeek rate-limiting → timeouts → JSON decode crashes.

They're not independent. Run as one sequence. Green individually ≠ green together.

## Suite location

```
/opt/ara/tests/
├── full_battery.py                  # canonical unified suite (61 assertions, live LLM)
├── gate_synth.py                    # synthesis pass gates (13 assertions, live LLM)
├── gate_retry.py                    # retry logic gates (7 assertions, live LLM)
├── test_action_item_drift.py        # two-axis state drift regression (16 assertions)
├── test_write_path_roundtrip.py     # PATCH state machine round-trip (15 assertions)
└── test_pending_confirmation.py     # confirmation flow integrity (various)
```

**⚠️ gate_synth.py and gate_retry.py are standalone scripts, NOT pytest tests.**
They use their own `check()`/`passed`/`failed` counters with live LLM calls via `subprocess.run(["curl", ...])`. Running them through pytest collects 0 items. Always invoke directly:
```bash
cd /opt/ara && timeout 600 ./venv/bin/python tests/gate_synth.py
cd /opt/ara && timeout 600 ./venv/bin/python tests/gate_retry.py
```
They take 2-5 minutes each (live DeepSeek calls per assertion, 75s timeout per call). Exit code 0 means all passed; check stdout for `RESULT: X passed, Y failed`.

**⚠️ Run gate tests SEQUENTIALLY, never in parallel.** DeepSeek API rate-limits concurrent calls — parallel gate_synth + gate_retry + full_battery cause timeouts and JSON decode crashes (server returns empty body under load). Run one at a time with generous timeouts.

**⚠️ full_battery.py is also a standalone script,** not a pytest test file. It defines its own check/assertion framework and makes live LLM calls. Run directly:
```bash
cd /opt/ara && timeout 900 ./venv/bin/python tests/full_battery.py
```

Run all: `cd /opt/ara && ./venv/bin/python tests/full_battery.py`
Run drift: `cd /opt/ara && ./venv/bin/python tests/test_action_item_drift.py`
Run write-path: `cd /opt/ara && ./venv/bin/python tests/test_write_path_roundtrip.py`

## TA Architecture Review

When Greg provides a multi-issue build plan and wants architectural sign-off before implementation, delegate a comprehensive audit to the TA subagent (model: glm-5.2, provider: zai, reasoning: high). See `references/ta-architecture-review.md` for the full delegation workflow — pre-flight line-number validation, context assembly, audit criteria, and output format.
