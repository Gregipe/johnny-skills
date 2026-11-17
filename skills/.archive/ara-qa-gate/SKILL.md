---
name: ara-qa-gate
description: QA workflow for ARA — run before every deploy. Spawns a QA sub-agent, runs tests + lint, gates deploy on pass.
---

# ARA QA Gate

Always run QA before deploying to production.

## Architecture: Three-Layer Gate

Every deploy runs through three layers in sequence:

```
Layer 1: Syntax check  (py_compile)
Layer 2: Mypy scoping  (catches used-before-def, name-defined)
Layer 3: pytest        (**113+** deterministic regression tests)
```

All three must pass before the server restarts. If any layer fails, the deploy aborts before touching production.

## Architecture: Shared Utils Pattern

The test suite uses a **shared-utils architecture**: pure functions live in `tests/enforcer_utils.py` and are imported by BOTH the test files AND production code (`server.py` imports `detect_data_intent`, `detect_question`, `has_data_tool_call`).

This means:
- One definition of the logic — tests and production share it.
- Any change to the enforcer logic is tested automatically on next `pytest`.
- Invalidating the shared utils = test failure. No silent drift.

### When to add to enforcer_utils
Any pure logic that's currently inlined in `agent_chat()` should be extracted:
- Message classification (is this a question? does it have data intent?)
- Response parsing (does the response contain a valid tool call?)
- Text preprocessing (emoji stripping, normalization)

## Workflow

### Quick QA (terminal)

```bash
cd /opt/ara && /opt/ara/venv/bin/python3 -m pytest tests/ -v --tb=short
```

### Full QA gate (script)

```bash
/opt/ara/scripts/qa-gate.sh
```

Runs: syntax check → mypy (scoping) → 95+ regression tests. Exit 0 = pass, Exit 1 = fail.

The mypy layer uses `--check-untyped-defs` with `--disable-error-code` flags for SQLAlchemy noise:

```bash
/opt/ara/venv/bin/python3 -m mypy server.py \
  --ignore-missing-imports \
  --disable-error-code valid-type \
  --disable-error-code misc \
  --disable-error-code var-annotated \
  --disable-error-code call-overload \
  --disable-error-code assignment \
  --disable-error-code dict-item \
  --disable-error-code arg-type \
  --disable-error-code union-attr \
  --disable-error-code operator \
  --check-untyped-defs
```

The critical checks enabled by default are `name-defined` and `used-before-def`, which catch Python 3.12 scoping crashes (`UnboundLocalError`) at compile time. The disabled codes are all SQLAlchemy Column/value impedance false positives.

### Deploy gate

The simplest way to deploy:

```bash
ssh root@46.224.132.99 'cd /opt/ara && bash deploy.sh'
```

This does everything: git pull → three-layer QA gate → restart → verify.

### Daily watchdog (automated)

A Hermes cron job (`ARA Daily Watchdog`) runs every day at **6:00 AM IST** (00:30 UTC):

- `no_agent=true` (zero token cost, pure shell script)
- **Silent on pass** — delivers nothing when all tests pass
- **Alerts on fail** — delivers trace output to Greg if any test breaks
- Runs: `pytest -x --tb=short` on the server via SSH

The script lives at `~/.hermes/scripts/ara-watchdog.sh`.

## Running QA via sub-agent

```python
delegate_task(
    goal="Run ARA QA gate against /opt/ara",
    context="The QA gate runs pytest and lint. Only pass if all tests pass. Do not deploy if tests fail.",
    toolsets=["terminal", "file"],
)
```

## Test layout

```
/opt/ara/tests/
├── __init__.py
├── enforcer_utils.py          # Shared pure functions (imported by tests AND server.py)
├── test_enforcer.py           # Enforcer logic: intent, question, tool detection, phantom updates
├── test_set_cron.py           # set_cron arg validation + DB insertion
├── test_dedup.py              # WhatsApp dedup: file persistence, expiry, corruption
├── test_question_detection.py # Question/intent detection edge cases + enforcer logic
├── test_voice_pipeline.py     # Voice dedup, transcript, audio validation
├── test_baileys_init.py       # WhatsApp client init sanity — catches __init__ regression
├── test_refactor_smoke.py     # Smoke tests for extracted app/ modules (config, schemas, dedup, utils, db)
├── Makefile                   # test, test-enforcer, test-cron, lint, qa targets
└── pyproject.toml             # pytest config
```

## When to update tests

- Adding a new data-modifying tool → add the tool name to `DATA_TOOLS` in `enforcer_utils.py`
- Changing enforcer logic → update `should_fire_enforcer` tests first (RED-GREEN)
- Fixing a production crash → add a regression test that reproduces the crash
- **Reliable log verification** → use line-based journal cursor capture instead of time-windowed grep. See `references/line-based-log-capture.md`.
- **Extracting code into a new module** → add a smoke test file

## Architecture Changes: Additional Verification

When replacing a large block of code (confirmation gate, tool execution flow, response building), **the QA gate is necessary but not sufficient.** The old code had implicit behaviors that weren't explicitly tested. Run these extra checks:

### Pre-deploy coverage audit

Before deploying an architecture change, grep for all implicit behaviors the old code had:

1. **Tool return value patterns** — Search for capital-bracket patterns in tool return strings: `[SUGGEST_DEAL:]`, `[WHATSAPP:]`, `[CANCEL:]`, `[KB:]`, `[SEARCH:]`. These are embedded directives the old code's post-execution section handled. The new code must handle the same patterns.

2. **Per-tool special cases** — The old code had special-case handling per tool:
   - `update_lead` voice notes with email/phone/name (STT guard)
   - `create_lead` deals with `[SUGGEST_DEAL:]` (deal suggestion)
   - `send_whatsapp` / `update_lead_stage` with canned response (response format)
   - `cancel_scheduled` with "nothing to cancel" (response format)
   - `set_cron` with cron config (response format)

3. **Response format from raw tool output** — If removing the post-execution LLM call, raw tool output needs prefix stripping (remove `✅ Name:` prefix from action text, normalize whitespace).

### Pre-deploy manual flow test

Run on the actual server before the final deploy commit:

```bash
# 1. Voice note create_lead (the most common regression)
curl -s -X POST http://localhost:8766/api/agent/chat/TENANT_ID \
  -H "Content-Type: application/json" \
  -d '{"message": "create a lead for Test User at Test Corp, phone 9876543210"}'

# 2. Voice note with data dictation (create_lead should ask, not execute)
curl -s -X POST http://localhost:8766/api/agent/chat/TENANT_ID \
  -H "Content-Type: application/json" \
  -d '{"message": "create a lead for Jimmie Tete at Bajaj, phone 0123456789"}'
# Expected: response contains proposed values, NO tool was executed in DB

# 3. Pending proposal confirmation
# First send create_lead, capture response, then send "yes" or "go ahead"

# 4. SUGGEST_DEAL follow-up
# Create a lead with a company name — response should ask about creating a deal

# 5. Direct command (should execute immediately)
curl -s -X POST http://localhost:8766/api/agent/chat/TENANT_ID \
  -H "Content-Type: application/json" \
  -d '{"message": "move Rajesh to reached_out stage"}'
```

### Rollback plan

If the deploy causes a regression, the rollback is immediate:

```bash
git revert HEAD
bash deploy.sh
```

The previous commit is always a working state. Architecture changes should be
in a single commit (not spread across 3+) for easy one-command revert.

## Python 3.12 Scoping Crash Pattern

**Signal:** `cannot access local variable 'X' where it is not associated with a value`

**Root cause:** Python 3.12+ treats ANY variable assigned ANYWHERE in a function as local to the entire function, even if the assignment is inside a nested `try/except` or comes after the first usage.

**We hit this pattern TWICE in one session:**
1. `_DEDUP_LAST_SAVE` — module-level variable assigned in `whatsapp_inbound_webhook()`. Fixed with `global _DEDUP_LAST_SAVE`.
2. `ScheduledAction` — a `from database import ScheduledAction` at line ~4723 (inside `execute_tool()` for a different tool handler) shadowed the module-level import. The `set_cron` handler used `ScheduledAction(...)` at line ~4625, BEFORE the local import, causing the crash. Fixed by adding `from database import ScheduledAction` at the top of the `set_cron` handler.

**Prevention:**
- When a function assigns to a module-level variable, add `global VARNAME` at the top of the function.
- When using a model class inside a function that's part of a long `execute_tool` function, import it locally at the TOP of that tool handler, not deeper in the file.
- Run `mypy --strict` — it catches these at compile time.
- Add a regression test that exercises the import path.
- **Best prevention: extract shared mutable state into its own module** (`app/dedup.py` pattern). A dedicated module with explicit `save()`/`load()`/`try_save()`/`register()` functions eliminates `global` declarations entirely — the module owns its own state and consumers never assign to it directly.

**How to test for this pattern:** Before adding a new tool handler to `execute_tool()`, check if any existing `from database import ...` statements in the same function could shadow the import. If yes, add the import at the top of your new handler block.
